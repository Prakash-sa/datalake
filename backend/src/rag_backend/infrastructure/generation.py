"""Generation providers.

The app can generate through an external Ollama daemon or a local ``llama.cpp``
runtime. The service code depends on this small boundary so the desktop app can
be self-contained when a GGUF model is bundled.
"""

from __future__ import annotations

import json
import logging
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from rag_backend.errors import ErrorCode, GenerationError, ModelUnavailableError
from rag_backend.infrastructure.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

GENERATION_TIMEOUT_SECONDS = 180
HEALTH_TIMEOUT_SECONDS = 30
SERVER_START_TIMEOUT_SECONDS = 60
LLAMA_SERVER_NAMES = ("llama-server", "/opt/homebrew/bin/llama-server")
LLAMA_CLI_NAMES = ("llama", "/opt/homebrew/bin/llama")
LLAMA_SIMPLE_NAMES = ("llama-simple", "/opt/homebrew/bin/llama-simple")

LLAMA_CHILD_CODE = r"""
from __future__ import annotations

import json
import sys

request = json.loads(sys.stdin.read())

try:
    from llama_cpp import Llama

    llm = Llama(
        model_path=request["model_path"],
        n_ctx=int(request["context_window"]),
        n_gpu_layers=int(request["gpu_layers"]),
        verbose=False,
    )
    result = llm(
        request["prompt"],
        max_tokens=int(request["max_tokens"]),
        temperature=float(request["temperature"]),
        stop=request["stop"] or ["</s>"],
        stream=False,
    )
    choices = result.get("choices", []) if isinstance(result, dict) else []
    text = ""
    if choices and isinstance(choices[0], dict):
        text = str(choices[0].get("text") or "")
    print(json.dumps({"text": text}))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    raise SystemExit(1)
"""


class GenerationProvider(Protocol):
    """Common generation surface used by the RAG service."""

    name: str
    model_name: str

    def generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> str:
        """Return a complete generated answer."""

    def stream_generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[str]:
        """Yield generated tokens."""

    def health(self) -> dict[str, object]:
        """Report readiness without document or prompt content."""


class OllamaGenerationProvider:
    """Generation provider backed by a local Ollama daemon."""

    name = "ollama"

    def __init__(self, client: OllamaClient, model: str) -> None:
        self.client = client
        self.model_name = model

    def generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> str:
        return self.client.generate(
            prompt,
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )

    def stream_generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[str]:
        yield from self.client.stream_generate(
            prompt,
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            cancel=cancel,
        )

    def health(self) -> dict[str, object]:
        ollama = self.client.check_health()
        installed = ollama.get("installed_models", [])
        ready = ollama.get("status") == "ready" and self.model_name in installed
        return {
            "status": "ready" if ready else "degraded",
            "provider": self.name,
            "model": self.model_name,
            "installed_models": installed,
            "ollama": ollama,
        }


class LlamaCppGenerationProvider:
    """Generation provider backed by llama.cpp bindings in a child process."""

    name = "local"

    def __init__(
        self,
        model_path: str,
        *,
        model_alias: str = "local-gguf",
        context_window: int = 4096,
        max_tokens: int = 256,
        gpu_layers: int = 12,
    ) -> None:
        self.model_path = str(Path(model_path).expanduser())
        self.model_name = model_alias
        self.context_window = context_window
        self.max_tokens = max_tokens
        self.gpu_layers = gpu_layers
        self._load_error: str | None = None
        self._health_cache: dict[str, object] | None = None
        self._server_process: subprocess.Popen[str] | None = None
        self._server_url: str | None = None
        self._server_error: str | None = None
        self._server_lock = threading.Lock()
        self._llama_server = self._find_executable(LLAMA_SERVER_NAMES)
        self._llama_cli = self._find_executable(LLAMA_CLI_NAMES)
        self._llama_simple = self._find_llama_simple()

    def _missing_model_error(self) -> str | None:
        if not Path(self.model_path).is_file():
            return f"Local generation model not found: {self.model_path}"
        return None

    @staticmethod
    def _crash_message(returncode: int) -> str:
        if returncode < 0:
            return (
                "Local generation runtime crashed while loading the model; "
                "switch to Ollama or install a compatible llama.cpp runtime"
            )
        return "Local generation process failed"

    @staticmethod
    def _find_executable(candidates: tuple[str, ...]) -> str | None:
        for candidate in candidates:
            resolved = shutil.which(candidate) if "/" not in candidate else candidate
            if resolved and Path(resolved).is_file():
                return resolved
        return None

    @classmethod
    def _find_llama_simple(cls) -> str | None:
        return cls._find_executable(LLAMA_SIMPLE_NAMES)

    def _runtime_name(self) -> str:
        if self._llama_server:
            return "llama-server"
        if self._llama_cli:
            return "llama-cli"
        if self._llama_simple:
            return "llama-simple"
        return "llama-cpp-python"

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _json_request(
        url: str,
        payload: dict[str, object] | None = None,
        *,
        timeout: int = GENERATION_TIMEOUT_SECONDS,
    ) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
        if not body:
            return {}
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}

    def _server_is_running(self) -> bool:
        return self._server_process is not None and self._server_process.poll() is None

    def _wait_for_server(self, timeout: int = SERVER_START_TIMEOUT_SECONDS) -> None:
        if self._server_url is None:
            raise ModelUnavailableError("Local generation server was not started")

        started_at = time.monotonic()
        last_error = ""
        while time.monotonic() - started_at < timeout:
            if self._server_process is not None and self._server_process.poll() is not None:
                stderr = ""
                if self._server_process.stderr is not None:
                    try:
                        stderr = self._server_process.stderr.read()
                    except Exception:
                        stderr = ""
                message = (
                    stderr.strip().splitlines()[-1] if stderr.strip() else "llama-server exited"
                )
                raise ModelUnavailableError(message)
            try:
                self._json_request(f"{self._server_url}/health", timeout=2)
                return
            except urllib.error.HTTPError as exc:
                last_error = str(exc)
                if exc.code < 500:
                    return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.25)

        raise ModelUnavailableError(f"Timed out starting llama-server: {last_error}")

    def _ensure_server(self) -> str:
        missing = self._missing_model_error()
        if missing is not None:
            self._load_error = missing
            raise ModelUnavailableError(missing)
        if self._llama_server is None:
            raise ModelUnavailableError("llama-server is not installed")

        with self._server_lock:
            if self._server_is_running() and self._server_url is not None:
                return self._server_url

            port = self._find_free_port()
            self._server_url = f"http://127.0.0.1:{port}"
            self._server_process = subprocess.Popen(
                [
                    self._llama_server,
                    "-m",
                    self.model_path,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--ctx-size",
                    str(self.context_window),
                    "--gpu-layers",
                    str(self.gpu_layers),
                    "--parallel",
                    "1",
                    "--no-webui",
                    "--log-disable",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self._wait_for_server()
            except Exception as exc:
                self.close()
                self._server_error = str(exc)
                self._load_error = str(exc)
                raise
            logger.info("Started llama-server for %s at %s", self.model_name, self._server_url)
            self._server_error = None
            return self._server_url

    @staticmethod
    def _completion_text(result: dict[str, object]) -> str:
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        return str(first.get("text") or "")

    def _generate_via_server(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> str:
        server_url = self._ensure_server()
        result = self._json_request(
            f"{server_url}/v1/completions",
            {
                "model": self.model_name,
                "prompt": prompt,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature,
                **({"stop": stop} if stop else {}),
                "stream": False,
            },
        )
        return self._completion_text(result)

    def _stream_via_server(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None,
        stop: list[str] | None,
        cancel: threading.Event | None,
    ) -> Iterator[str]:
        server_url = self._ensure_server()
        payload = json.dumps(
            {
                "model": self.model_name,
                "prompt": prompt,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature,
                **({"stop": stop} if stop else {}),
                "stream": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{server_url}/v1/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=GENERATION_TIMEOUT_SECONDS) as response:
            for raw_line in response:
                if cancel is not None and cancel.is_set():
                    logger.info("Local server generation cancelled by caller")
                    return
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    return
                try:
                    text = self._completion_text(json.loads(data))
                except json.JSONDecodeError:
                    continue
                if text:
                    yield text

    @staticmethod
    def _extract_llama_simple_text(stdout: str, prompt: str) -> str:
        start = stdout.rfind(prompt)
        text = stdout[start + len(prompt) :] if start >= 0 else stdout
        for marker in ("main: decoded", "llama_perf_", "~llama_context:"):
            if marker in text:
                text = text.split(marker, 1)[0]
        return text.strip(" \t\r\n-")

    @staticmethod
    def _extract_llama_cli_text(text: str) -> str:
        marker = "Assistant:"
        if marker in text:
            text = text.rsplit(marker, 1)[1]
        return text.strip()

    def _run_llama_cli(
        self,
        prompt: str,
        temperature: float,
        *,
        max_tokens: int,
        context_window: int,
        stop: list[str] | None,
        timeout: int,
    ) -> str:
        if self._llama_cli is None:
            raise ModelUnavailableError(
                "llama CLI is not installed; install llama.cpp or switch to Ollama"
            )

        output_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="rag-llama-",
                suffix=".txt",
                delete=False,
            ) as out:
                output_path = Path(out.name)
            completed = subprocess.run(
                [
                    self._llama_cli,
                    "cli",
                    "-m",
                    self.model_path,
                    "-p",
                    prompt,
                    "-n",
                    str(max_tokens),
                    "--ctx-size",
                    str(context_window),
                    "--gpu-layers",
                    str(self.gpu_layers),
                    "--temp",
                    str(temperature),
                    "--single-turn",
                    "--no-display-prompt",
                    "--no-show-timings",
                    "--simple-io",
                    "--log-disable",
                    *[item for marker in (stop or []) for item in ("--reverse-prompt", marker)],
                    "-o",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            if completed.returncode != 0:
                message = self._child_error(completed.stdout, completed.stderr)
                message = message or self._crash_message(completed.returncode)
                self._load_error = message
                if completed.returncode < 0:
                    raise ModelUnavailableError(message)
                raise GenerationError(message, code=ErrorCode.GENERATION_FAILED)
            output = output_path.read_text(encoding="utf-8", errors="replace")
            return self._extract_llama_cli_text(output)
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                "Local generation timed out",
                code=ErrorCode.GENERATION_TIMEOUT,
            ) from exc
        finally:
            if output_path is not None:
                output_path.unlink(missing_ok=True)

    def _run_llama_simple(
        self,
        prompt: str,
        *,
        max_tokens: int,
        timeout: int,
    ) -> str:
        if self._llama_simple is None:
            raise ModelUnavailableError(
                "llama-simple is not installed; install llama.cpp or switch to Ollama"
            )

        try:
            completed = subprocess.run(
                [
                    self._llama_simple,
                    "-m",
                    self.model_path,
                    "-n",
                    str(max_tokens),
                    "-ngl",
                    str(self.gpu_layers),
                    prompt,
                ],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                "Local generation timed out",
                code=ErrorCode.GENERATION_TIMEOUT,
            ) from exc

        if completed.returncode != 0:
            message = self._child_error(completed.stdout, completed.stderr)
            message = message or self._crash_message(completed.returncode)
            self._load_error = message
            if completed.returncode < 0:
                raise ModelUnavailableError(message)
            raise GenerationError(message, code=ErrorCode.GENERATION_FAILED)

        return self._extract_llama_simple_text(completed.stdout, prompt)

    def _run_python_child(
        self,
        prompt: str,
        temperature: float,
        *,
        max_tokens: int | None = None,
        context_window: int | None = None,
        stop: list[str] | None = None,
        timeout: int = GENERATION_TIMEOUT_SECONDS,
    ) -> str:
        missing = self._missing_model_error()
        if missing is not None:
            self._load_error = missing
            raise ModelUnavailableError(missing)

        payload = {
            "model_path": self.model_path,
            "context_window": context_window or self.context_window,
            "max_tokens": max_tokens or self.max_tokens,
            "prompt": prompt,
            "temperature": temperature,
            "gpu_layers": self.gpu_layers,
            "stop": stop,
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-c", LLAMA_CHILD_CODE],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GenerationError(
                "Local generation timed out",
                code=ErrorCode.GENERATION_TIMEOUT,
            ) from exc

        stdout = completed.stdout.strip()
        if completed.returncode != 0:
            detail = self._child_error(stdout, completed.stderr)
            message = detail or self._crash_message(completed.returncode)
            self._load_error = message
            if completed.returncode < 0:
                raise ModelUnavailableError(message)
            raise GenerationError(message, code=ErrorCode.GENERATION_FAILED)

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise GenerationError(
                "Local generation returned an invalid response",
                code=ErrorCode.GENERATION_FAILED,
            ) from exc

        if isinstance(result, dict) and result.get("error"):
            message = str(result["error"])
            self._load_error = message
            raise GenerationError(message, code=ErrorCode.GENERATION_FAILED)
        if isinstance(result, dict):
            return str(result.get("text") or "")
        return ""

    def _run_child(
        self,
        prompt: str,
        temperature: float,
        *,
        max_tokens: int | None = None,
        context_window: int | None = None,
        stop: list[str] | None = None,
        timeout: int = GENERATION_TIMEOUT_SECONDS,
    ) -> str:
        missing = self._missing_model_error()
        if missing is not None:
            self._load_error = missing
            raise ModelUnavailableError(missing)

        tokens = max_tokens or self.max_tokens
        ctx = context_window or self.context_window
        if self._llama_server is not None and context_window is None:
            return self._generate_via_server(
                prompt, temperature, max_tokens=max_tokens, stop=stop
            )
        if self._llama_cli is not None:
            return self._run_llama_cli(
                prompt,
                temperature,
                max_tokens=tokens,
                context_window=ctx,
                stop=stop,
                timeout=timeout,
            )
        if self._llama_simple is not None:
            return self._run_llama_simple(prompt, max_tokens=tokens, timeout=timeout)
        return self._run_python_child(
            prompt,
            temperature,
            max_tokens=tokens,
            context_window=ctx,
            stop=stop,
            timeout=timeout,
        )

    @staticmethod
    def _child_error(stdout: str, stderr: str) -> str:
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("error"):
                return str(parsed["error"])
        return stderr.strip().splitlines()[-1] if stderr.strip() else ""

    @staticmethod
    def _token_text(chunk: object) -> str:
        if not isinstance(chunk, dict):
            return ""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        return str(first.get("text") or "")

    def generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> str:
        return self._run_child(prompt, temperature, max_tokens=max_tokens, stop=stop)

    def stream_generate(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[str]:
        if self._llama_server is not None:
            yield from self._stream_via_server(prompt, temperature, max_tokens, stop, cancel)
            return
        if cancel is not None and cancel.is_set():
            logger.info("Local generation cancelled by caller before start")
            return
        text = self.generate(prompt, temperature, max_tokens=max_tokens, stop=stop)
        if cancel is not None and cancel.is_set():
            logger.info("Local generation cancelled by caller after completion")
            return
        if text:
            yield text

    def _probe_health(self) -> dict[str, object]:
        try:
            if self._llama_server is not None:
                self._ensure_server()
            else:
                self._run_child(
                    "OK",
                    0.0,
                    max_tokens=1,
                    context_window=128,
                    timeout=HEALTH_TIMEOUT_SECONDS,
                )
        except ModelUnavailableError as exc:
            return {
                "status": "degraded",
                "provider": self.name,
                "model": self.model_name,
                "model_path": self.model_path,
                "runtime": self._runtime_name(),
                "gpu_layers": self.gpu_layers,
                "max_tokens": self.max_tokens,
                "error": str(exc),
            }
        except GenerationError as exc:
            return {
                "status": "degraded",
                "provider": self.name,
                "model": self.model_name,
                "model_path": self.model_path,
                "runtime": self._runtime_name(),
                "gpu_layers": self.gpu_layers,
                "max_tokens": self.max_tokens,
                "error": str(exc),
            }
        return {
            "status": "ready",
            "provider": self.name,
            "model": self.model_name,
            "model_path": self.model_path,
            "runtime": self._runtime_name(),
            "gpu_layers": self.gpu_layers,
            "max_tokens": self.max_tokens,
        }

    def health(self) -> dict[str, object]:
        path = Path(self.model_path)
        if not path.is_file():
            return {
                "status": "degraded",
                "provider": self.name,
                "model": self.model_name,
                "model_path": self.model_path,
                "runtime": self._runtime_name(),
                "gpu_layers": self.gpu_layers,
                "max_tokens": self.max_tokens,
                "error": "local model file missing",
            }
        if self._load_error is not None:
            return {
                "status": "degraded",
                "provider": self.name,
                "model": self.model_name,
                "model_path": self.model_path,
                "runtime": self._runtime_name(),
                "gpu_layers": self.gpu_layers,
                "max_tokens": self.max_tokens,
                "error": self._load_error,
            }
        if self._health_cache is None:
            self._health_cache = self._probe_health()
        return self._health_cache

    def close(self) -> None:
        process = self._server_process
        self._server_process = None
        self._server_url = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def build_generation_provider(
    provider: str,
    *,
    ollama_client: OllamaClient,
    model: str,
    local_model_path: str,
    local_gpu_layers: int = 12,
    local_max_tokens: int = 256,
) -> GenerationProvider:
    """Build the configured generation provider."""
    if provider == "ollama":
        return OllamaGenerationProvider(ollama_client, model)
    if provider == "local":
        return LlamaCppGenerationProvider(
            local_model_path,
            model_alias=model,
            gpu_layers=local_gpu_layers,
            max_tokens=local_max_tokens,
        )
    raise ValueError(f"Unsupported generation provider: {provider}")
