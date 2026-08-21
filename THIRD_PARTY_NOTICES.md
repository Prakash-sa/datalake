# Third-Party Notices

This project bundles third-party software and one machine-learning model. This
file records what ships, where it came from, and under which licence.

Regenerate the dependency list from the lockfiles before any binary release;
the versions below are the ones present when this file was last reviewed.

---

## Bundled model

The desktop build ships model weights inside the installer so that importing,
searching, and default local answer generation work with no network access.

| | |
| --- | --- |
| Model | `all-MiniLM-L6-v2` (ONNX export) |
| Purpose | Sentence embeddings, 384 dimensions |
| Source | `https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz` |
| Archive SHA-256 | `913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3` |
| Licence | Apache-2.0 |
| Origin | [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) |
| Installed by | `backend/scripts/fetch_embedding_model.py` |

The archive is verified against the checksum above at build time. The weights are
not committed to this repository.

## Bundled generation model

Release builds fetch a GGUF generation model through
`backend/scripts/fetch_generation_model.py`, using `LOCAL_LLM_GGUF_URL` and
`LOCAL_LLM_GGUF_SHA256` provided by CI secrets. Record the exact model source,
digest, and licence here before publishing a binary release.

Models downloaded by the user through Ollama are **not** distributed here. Their
licences are set by their publishers and are not covered by this project's
licence.

---

## Backend dependencies

| Package | Version | Licence |
| --- | --- | --- |
| fastapi | 0.141.1 | MIT |
| uvicorn | 0.52.3 | BSD-3-Clause |
| pydantic | 2.13.4 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| chromadb | 1.5.9 | Apache-2.0 |
| onnxruntime | 1.28.0 | MIT |
| tokenizers | 0.23.1 | Apache-2.0 |
| numpy | 2.5.2 | BSD-3-Clause and others |
| langchain, langchain-core, langchain-ollama | 1.x | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| python-docx | 1.2.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| gunicorn | 26.0.0 | MIT |
| pypdf | 6.x | BSD-3-Clause |
| llama-cpp-python | 0.3.x | MIT |

SQLite, including its FTS5 extension, ships with CPython and is in the public
domain.

## Desktop and frontend dependencies

| Package | Licence |
| --- | --- |
| Electron | MIT |
| electron-builder, @electron/fuses | MIT |
| Next.js | MIT |
| React, React DOM | MIT |
| Tailwind CSS, PostCSS, Autoprefixer | MIT |
| lucide-react | ISC |

## External software

**Ollama** is installed separately by the user and is not distributed with this
application. It is optional; the packaged app uses the bundled local generation
model by default.

---

## Release checklist

- [ ] Regenerate this file from `backend/uv.lock` and `frontend/package-lock.json`
- [ ] Confirm the bundled model checksum still matches
- [ ] Record the bundled GGUF generation model source, digest, and licence
- [ ] Attach the generated SBOM to the release
