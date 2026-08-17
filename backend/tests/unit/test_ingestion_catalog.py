from pathlib import Path

from rag_backend.application.ingestion_service import build_ingested_document, chunk_text
from rag_backend.infrastructure.catalog_store import CatalogStore


def test_chunk_text_preserves_content():
    text = "First paragraph.\n\n" + ("Second paragraph. " * 200)

    chunks = chunk_text(text, chunk_size=300, overlap=40)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert "First paragraph." in chunks[0]


def test_build_ingested_document_for_text_file(tmp_path: Path):
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n\nProduction readiness requires citations.", encoding="utf-8")

    result = build_ingested_document(source, "embed-model", "llm-model")

    assert result["document"]["title"] == "notes.md"
    assert result["document"]["metadata"]["chunk_count"] == len(result["chunks"])
    assert result["chunks"][0]["metadata"]["source_name"] == "notes.md"


def test_catalog_persists_documents_and_chunks(tmp_path: Path):
    store = CatalogStore(str(tmp_path / "app.db"))
    source = tmp_path / "notes.txt"
    source.write_text("Local RAG memory is stored on disk.", encoding="utf-8")
    result = build_ingested_document(source, "embed-model", "llm-model")

    store.upsert_document(result["document"], result["chunks"])

    documents = store.list_documents()
    assert len(documents) == 1
    assert documents[0]["chunk_count"] == len(result["chunks"])
    assert store.get_document_by_hash(result["document"]["source_hash"]) is not None

    assert store.delete_document(result["document"]["id"]) is True
    assert store.list_documents() == []


def test_catalog_fts_search(tmp_path: Path):
    store = CatalogStore(str(tmp_path / "app.db"))
    source = tmp_path / "retrieval.txt"
    source.write_text(
        "Reciprocal rank fusion combines dense and lexical retrieval.", encoding="utf-8"
    )
    result = build_ingested_document(source, "embed-model", "llm-model")
    store.upsert_document(result["document"], result["chunks"])

    matches = store.search_fts("lexical retrieval", limit=5)

    assert len(matches) == 1
    assert matches[0]["id"] == result["chunks"][0]["id"]
