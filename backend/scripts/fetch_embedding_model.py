#!/usr/bin/env python3
"""Download the local embedding model into the sidecar bundle.

The app must work with no external software installed, so the ONNX model is
shipped rather than fetched on first run. This runs at build time; the runtime
never downloads anything.

Artifacts are the same all-MiniLM-L6-v2 export Chroma distributes, verified
against its published SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"
ARCHIVE_URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
ARCHIVE_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"

# Only what inference needs; the archive also carries vocab and config files
# that the tokenizer.json already embeds.
REQUIRED_FILES = ("model.onnx", "tokenizer.json")

DEFAULT_TARGET = Path(__file__).resolve().parents[1] / "src" / "rag_backend" / "models" / MODEL_NAME


def _download(url: str, destination: Path) -> None:
    print(f"[model] downloading {url}")
    with urllib.request.urlopen(url, timeout=300) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def _verify(path: Path, expected: str) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected:
        raise SystemExit(f"[model] checksum mismatch\n  expected {expected}\n  actual   {actual}")
    print("[model] checksum verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()

    target: Path = args.target
    if not args.force and all((target / name).is_file() for name in REQUIRED_FILES):
        print(f"[model] already present in {target}")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "onnx.tar.gz"
        _download(ARCHIVE_URL, archive)
        _verify(archive, ARCHIVE_SHA256)

        with tarfile.open(archive) as tar:
            # Extract only the files inference needs, and refuse absolute or
            # parent-relative members so a malicious archive cannot escape.
            for member in tar.getmembers():
                name = Path(member.name).name
                if name not in REQUIRED_FILES or not member.isfile():
                    continue
                if Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                    raise SystemExit(f"[model] refusing unsafe archive member: {member.name}")
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                (target / name).write_bytes(extracted.read())

    missing = [name for name in REQUIRED_FILES if not (target / name).is_file()]
    if missing:
        raise SystemExit(f"[model] archive did not contain: {', '.join(missing)}")

    total = sum((target / name).stat().st_size for name in REQUIRED_FILES)
    print(f"[model] installed {MODEL_NAME} into {target} ({total / 1e6:.1f}MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
