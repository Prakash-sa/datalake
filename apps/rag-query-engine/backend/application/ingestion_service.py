"""
Local file ingestion, parsing, and chunking.
"""

import hashlib
import html
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Tuple
from xml.etree import ElementTree


PARSER_VERSION = "local-parser-v1"
CHUNKER_VERSION = "recursive-char-v1"
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".docx", ".pdf"}


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return html.unescape(" ".join(self.parts))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_file(path: Path, max_size_mb: int = 200) -> None:
    if not path.exists():
        raise ValueError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {path}")
    if path.is_symlink() and not path.resolve().is_file():
        raise ValueError(f"Symlink does not resolve to a readable file: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    if path.stat().st_size > max_size_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {max_size_mb}MB limit: {path}")


def parse_file(path: Path) -> Tuple[str, Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return parse_text_file(path), {"content_type": "text/markdown" if suffix != ".txt" else "text/plain"}
    if suffix in {".html", ".htm"}:
        return parse_html_file(path), {"content_type": "text/html"}
    if suffix == ".docx":
        return parse_docx_file(path), {"content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if suffix == ".pdf":
        return parse_pdf_file(path), {"content_type": "application/pdf"}
    raise ValueError(f"Unsupported file type: {suffix}")


def parse_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_html_file(path: Path) -> str:
    parser = HTMLTextExtractor()
    parser.feed(parse_text_file(path))
    return parser.text()


def parse_docx_file(path: Path) -> str:
    paragraphs: List[str] = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        if texts:
            paragraphs.append("".join(texts))
    return "\n\n".join(paragraphs)


def parse_pdf_file(path: Path) -> str:
    try:
        import fitz  # type: ignore
    except ImportError as e:
        raise ValueError("PDF ingestion requires PyMuPDF. Install the backend requirements first.") from e

    parts: List[str] = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()
            if text:
                parts.append(f"\n\n[Page {page_index + 1}]\n{text}")
    return "\n".join(parts)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> List[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        window = normalized[start:end]
        split_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
        if split_at > chunk_size * 0.4 and end < len(normalized):
            end = start + split_at + 1
            window = normalized[start:end]
        chunks.append(window.strip())
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


def build_ingested_document(path: Path, embedding_model: str, llm_model: str) -> Dict[str, Any]:
    validate_file(path)
    source_hash = sha256_file(path)
    text, parser_metadata = parse_file(path)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError(f"No extractable text found in {path}")

    document_id = f"doc_{source_hash[:24]}"
    chunk_records = []
    for idx, chunk in enumerate(chunks):
        content_hash = sha256_text(chunk)
        chunk_records.append(
            {
                "id": f"{document_id}_chunk_{idx:05d}",
                "chunk_index": idx,
                "content": chunk,
                "content_hash": content_hash,
                "metadata": {
                    "source_document_id": document_id,
                    "source_path": str(path),
                    "source_name": path.name,
                    "source_hash": source_hash,
                    "chunk_index": idx,
                    "parser_version": PARSER_VERSION,
                    "chunker_version": CHUNKER_VERSION,
                    "embedding_model": embedding_model,
                },
            }
        )

    return {
        "document": {
            "id": document_id,
            "source_path": str(path),
            "title": path.name,
            "source_hash": source_hash,
            "content_type": parser_metadata["content_type"],
            "parser_version": PARSER_VERSION,
            "chunker_version": CHUNKER_VERSION,
            "embedding_model": embedding_model,
            "llm_model": llm_model,
            "metadata": {
                "source_name": path.name,
                "source_extension": path.suffix.lower(),
                "source_size_bytes": path.stat().st_size,
                "chunk_count": len(chunk_records),
            },
        },
        "chunks": chunk_records,
    }
