"""Ollama HTTP adapter.

Talks to a local Ollama daemon over its REST API. Uses ``urllib`` rather than a
third-party client so the PyInstaller sidecar bundle stays small.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from rag_backend.errors import (
    ErrorCode,
    GenerationError,
    GenerationTimeoutError,
    ModelUnavailableError,
    RagError,
    classify_ollama_exception,
)

logger = logging.getLogger(__name__)

TAGS_TIMEOUT_SECONDS = 3
# The UI polls /readiness and /models together, and Activity re-polls while a
# job runs, so an uncached probe means several network round trips per second.
HEALTH_CACHE_SECONDS = 2.0
PULL_TIMEOUT_SECONDS = 60 * 60
# Wall-clock ceiling for a whole generation. The plan requires real request
# timeouts rather than the unbounded waits langchain's invoke() performs.
GENERATION_TIMEOUT_SECONDS = 120


class OllamaClient:
    """Thin client for the subset of the Ollama API this backend needs."""

    def __init__(self, base_url: str, required_models: list[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.required_models = required_models
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0
        # Only a change in outcome is worth logging; repeating an unchanged
        # failure once per poll buries everything else.
        self._last_logged: str | None = None

    def check_health(self, use_cache: bool = True) -> dict[str, Any]:
        """Report daemon reachability and whether required models are present.

        Cached briefly, because callers poll and a stopped daemon should not
        cost a network attempt per request.
        """
        if use_cache:
            with self._lock:
                fresh = time.monotonic() - self._cached_at < HEALTH_CACHE_SECONDS
                if self._cached is not None and fresh:
                    return self._cached

        result = self._probe()
        with self._lock:
            self._cached = result
            self._cached_at = time.monotonic()
        return result

    def _probe(self) -> dict[str, Any]:
        try:
            request = urllib.request.Request(
                f"{self.base_url}/api/tags", headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=TAGS_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))

            installed = {
                model.get("name") or model.get("model")
                for model in payload.get("models", [])
                if model.get("name") or model.get("model")
            }
            # Digests identify the exact weights behind a tag. A tag can be
            # repointed at new weights, so the digest is what tells us an index
            # was built with a different model than the one now installed.
            digests = {
                (model.get("name") or model.get("model")): model.get("digest", "")
                for model in payload.get("models", [])
                if model.get("name") or model.get("model")
            }
            # Size decides whether a model will actually run on this machine,
            # so it informs which one is selected when nothing is configured.
            sizes = {
                (model.get("name") or model.get("model")): int(model.get("size", 0) or 0)
                for model in payload.get("models", [])
                if model.get("name") or model.get("model")
            }
            # Accept a bare family name as satisfying a tagged requirement.
            aliases = installed | {model.split(":", 1)[0] for model in installed}
            missing = [model for model in self.required_models if model not in aliases]

            signature = f"ok:{sorted(missing)}"
            if signature != self._last_logged:
                logger.info(
                    "Ollama reachable at %s (%d model(s) missing)",
                    self.base_url,
                    len(missing),
                )
                self._last_logged = signature

            return {
                "status": "ready" if not missing else "degraded",
                "url": self.base_url,
                "required_models": self.required_models,
                "installed_models": sorted(installed),
                "missing_models": missing,
                "digests": digests,
                "sizes": sizes,
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            signature = f"error:{e}"
            if signature != self._last_logged:
                logger.warning("Ollama unreachable at %s: %s", self.base_url, e)
                self._last_logged = signature
            return {
                "status": "error",
                "url": self.base_url,
                "required_models": self.required_models,
                "installed_models": [],
                "missing_models": self.required_models,
                "digests": {},
                "sizes": {},
                "error": str(e),
            }

    def list_models(self) -> dict[str, Any]:
        """List installed models alongside the ones this backend requires."""
        health = self.check_health()
        return {
            "status": health.get("status", "error"),
            "ollama_url": self.base_url,
            "models": [{"name": model} for model in health.get("installed_models", [])],
            "required_models": health.get("required_models", []),
            "missing_models": health.get("missing_models", []),
            "error": health.get("error"),
        }

    def pull_model(self, name: str) -> dict[str, Any]:
        """Pull a model with a single non-streaming request."""
        try:
            payload = json.dumps({"name": name, "stream": False}).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/pull",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=PULL_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode("utf-8") or "{}")
            return {"status": "success", "model": name, "result": result}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return {"status": "error", "model": name, "error": str(e)}

    # -- Generation -----------------------------------------------------------

    def _generation_payload(
        self,
        prompt: str,
        model: str,
        temperature: float,
        stream: bool,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> bytes:
        options: dict[str, object] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop:
            options["stop"] = stop
        return json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": options,
            }
        ).encode("utf-8")

    def _generation_request(self, payload: bytes) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/x-ndjson",
            },
            method="POST",
        )

    @staticmethod
    def _as_rag_error(exc: Exception) -> RagError:
        """Translate a transport exception into a structured error."""
        code = classify_ollama_exception(exc)
        message = str(exc)
        if code is ErrorCode.GENERATION_TIMEOUT:
            return GenerationTimeoutError("Generation timed out", code=code)
        if code is ErrorCode.MODEL_UNAVAILABLE:
            return ModelUnavailableError(message, code=code)
        return GenerationError(message, code=code)

    def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        timeout: float = GENERATION_TIMEOUT_SECONDS,
    ) -> str:
        """Generate a complete answer, raising a structured error on failure."""
        try:
            request = self._generation_request(
                self._generation_payload(
                    prompt,
                    model,
                    temperature,
                    stream=False,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
        except Exception as e:
            raise self._as_rag_error(e) from e

        if payload.get("error"):
            raise ModelUnavailableError(str(payload["error"]), code=ErrorCode.MODEL_UNAVAILABLE)
        return payload.get("response", "")

    def stream_generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        timeout: float = GENERATION_TIMEOUT_SECONDS,
        cancel: threading.Event | None = None,
    ) -> Iterator[str]:
        """Yield generation tokens as they arrive.

        ``cancel`` is checked between chunks, so a caller can abandon a
        generation without waiting for the model to finish. The connection is
        closed on exit, which also stops Ollama producing further tokens.
        """
        try:
            request = self._generation_request(
                self._generation_payload(
                    prompt,
                    model,
                    temperature,
                    stream=True,
                    max_tokens=max_tokens,
                    stop=stop,
                )
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                for raw_line in response:
                    if cancel is not None and cancel.is_set():
                        logger.info("Generation cancelled by caller")
                        return

                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        # Ollama emits one JSON object per line; skip anything
                        # malformed rather than failing a partial answer.
                        logger.debug("Skipping malformed generation chunk")
                        continue

                    if chunk.get("error"):
                        raise ModelUnavailableError(
                            str(chunk["error"]), code=ErrorCode.MODEL_UNAVAILABLE
                        )

                    token = chunk.get("response", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        return
        except RagError:
            raise
        except Exception as e:
            raise self._as_rag_error(e) from e

    def stream_pull_model(
        self, name: str, cancel: threading.Event | None = None
    ) -> Iterator[dict[str, Any]]:
        """Pull a model, yielding Ollama's progress records as they arrive.

        Each record carries a ``status`` string and, while layers are
        downloading, ``completed`` and ``total`` byte counts. Cancellation is
        checked between records; closing the connection stops the transfer.
        """
        payload = json.dumps({"name": name, "stream": True}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/pull",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/x-ndjson",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=PULL_TIMEOUT_SECONDS) as response:
                for raw_line in response:
                    if cancel is not None and cancel.is_set():
                        logger.info("Model pull cancelled by caller")
                        return

                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed pull record")
                        continue

                    if record.get("error"):
                        raise ModelUnavailableError(
                            str(record["error"]), code=ErrorCode.MODEL_UNAVAILABLE
                        )
                    yield record
        except RagError:
            raise
        except Exception as e:
            raise self._as_rag_error(e) from e

    def model_digest(self, name: str) -> str | None:
        """Return the digest for an installed model, or None if unknown.

        Falls back to a bare family match, mirroring how ``check_health``
        accepts an untagged name as satisfying a tagged requirement.
        """
        digests = self.check_health().get("digests", {})
        if name in digests:
            return digests[name] or None
        family = name.split(":", 1)[0]
        for installed, digest in digests.items():
            if installed.split(":", 1)[0] == family:
                return digest or None
        return None
