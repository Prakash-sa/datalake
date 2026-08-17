"""Ollama HTTP adapter.

Talks to a local Ollama daemon over its REST API. Uses ``urllib`` rather than a
third-party client so the PyInstaller sidecar bundle stays small.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

TAGS_TIMEOUT_SECONDS = 3
PULL_TIMEOUT_SECONDS = 60 * 60


class OllamaClient:
    """Thin client for the subset of the Ollama API this backend needs."""

    def __init__(self, base_url: str, required_models: list[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.required_models = required_models

    def check_health(self) -> dict[str, Any]:
        """Report daemon reachability and whether required models are present."""
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
            # Accept a bare family name as satisfying a tagged requirement.
            aliases = installed | {model.split(":", 1)[0] for model in installed}
            missing = [model for model in self.required_models if model not in aliases]

            return {
                "status": "ready" if not missing else "degraded",
                "url": self.base_url,
                "required_models": self.required_models,
                "installed_models": sorted(installed),
                "missing_models": missing,
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            logger.warning("Ollama readiness failed: %s", e)
            return {
                "status": "error",
                "url": self.base_url,
                "required_models": self.required_models,
                "installed_models": [],
                "missing_models": self.required_models,
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
