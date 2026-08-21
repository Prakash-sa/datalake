"""Fetch the release GGUF generation model.

The model is intentionally not committed to git. Release builds provide the
download URL and checksum through CI secrets so the artifact is reproducible and
the selected model/license can be reviewed before distribution.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_DIR = Path(__file__).resolve().parents[1] / "src" / "rag_backend" / "models"
MODEL_PATH = MODEL_DIR / MODEL_FILENAME


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    url = os.environ.get("LOCAL_LLM_GGUF_URL")
    expected = os.environ.get("LOCAL_LLM_GGUF_SHA256", "").lower()
    allow_missing = os.environ.get("ALLOW_MISSING_LOCAL_LLM") == "1"

    if not url or not expected:
        if allow_missing:
            print(
                "LOCAL_LLM_GGUF_URL or LOCAL_LLM_GGUF_SHA256 is missing; "
                "continuing without a bundled generation model for this tester build.",
                file=sys.stderr,
            )
            return 0
        print(
            "LOCAL_LLM_GGUF_URL and LOCAL_LLM_GGUF_SHA256 are required for release "
            "packaging. Choose a distributable GGUF model, record its licence in "
            "THIRD_PARTY_NOTICES.md, and provide its checksum through CI secrets.",
            file=sys.stderr,
        )
        return 2

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.exists() and sha256(MODEL_PATH).lower() == expected:
        print(f"Generation model already present: {MODEL_PATH}")
        return 0

    with tempfile.NamedTemporaryFile(
        prefix=f"{MODEL_FILENAME}.",
        suffix=".tmp",
        dir=MODEL_DIR,
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, tmp_path)
        actual = sha256(tmp_path).lower()
        if actual != expected:
            print(
                f"Checksum mismatch for {url}\nexpected: {expected}\nactual:   {actual}",
                file=sys.stderr,
            )
            return 1
        tmp_path.replace(MODEL_PATH)
        print(f"Installed generation model at {MODEL_PATH}")
        return 0
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
