# Third-Party Notices

This project bundles third-party software and one machine-learning model. This
file records what ships, where it came from, and under which licence.

Regenerate the dependency list from the lockfiles before any binary release;
the versions below are the ones present when this file was last reviewed.

---

## ⚠️ Unresolved licence conflict

**PyMuPDF is dual-licensed under GNU AGPL-3.0 or a commercial Artifex licence.**
This project declares MIT. AGPL-3.0 is strong copyleft, so distributing a binary
that embeds PyMuPDF is not compatible with offering that binary under MIT.

Resolve before distributing builds. The options are:

1. Relicense this project under AGPL-3.0.
2. Obtain a commercial PyMuPDF licence from Artifex.
3. Replace PyMuPDF with a permissively licensed PDF parser, such as
   [`pypdf`](https://pypi.org/project/pypdf/) (BSD-3-Clause) or
   [`pdfminer.six`](https://pypi.org/project/pdfminer.six/) (MIT).

PyMuPDF is used only in `parse_pdf_file`, so option 3 is contained, though PDF
text-extraction quality would need re-evaluating against the eval corpus.

Building and running from source is unaffected; this concerns redistribution.

---

## Bundled model

The desktop build ships model weights inside the installer so that importing and
searching work with no network access.

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

## Models obtained by the user

Generation models are downloaded by the user through Ollama and are **not**
distributed here. Their licences are set by their publishers and are not covered
by this project's licence. Record any model the application recommends by
default, with its digest and licence, before release.

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
| **PyMuPDF** | **1.28.2** | **AGPL-3.0 or commercial — see above** |

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
application. It is optional and used only for generated prose answers.

---

## Release checklist

- [ ] Regenerate this file from `backend/uv.lock` and `frontend/package-lock.json`
- [ ] Resolve the PyMuPDF licence conflict above
- [ ] Confirm the bundled model checksum still matches
- [ ] Attach the generated SBOM to the release
