"""Tests for index fingerprint comparison."""

from __future__ import annotations

from rag_backend.domain.fingerprint import (
    INDEX_SCHEMA_VERSION,
    build_fingerprint,
    compare,
)


def fp(**overrides):
    base = build_fingerprint(
        embedding_model="qwen3-embedding:0.6b",
        embedding_digest="sha256:abc",
        chunker_version="recursive-char-v1",
        parser_version="local-parser-v1",
    )
    return {**base, **overrides}


def test_fingerprint_records_the_schema_version():
    assert fp()["index_schema_version"] == INDEX_SCHEMA_VERSION


def test_identical_configuration_matches():
    result = compare(fp(), fp())

    assert result["status"] == "match"
    assert result["rebuild_required"] is False
    assert result["changed"] == []


def test_no_stored_fingerprint_is_unknown_not_a_mismatch():
    # An empty index has nothing to rebuild.
    result = compare(None, fp())

    assert result["status"] == "unknown"
    assert result["rebuild_required"] is False


def test_changing_the_embedding_model_requires_a_rebuild():
    result = compare(fp(), fp(embedding_model="nomic-embed-text"))

    assert result["rebuild_required"] is True
    assert "embedding_model" in result["changed"]


def test_changing_the_embedding_digest_requires_a_rebuild():
    # A tag can be repointed at new weights without its name changing.
    result = compare(fp(), fp(embedding_digest="sha256:different"))

    assert result["rebuild_required"] is True
    assert "embedding_digest" in result["changed"]


def test_changing_the_index_schema_requires_a_rebuild():
    result = compare(fp(), fp(index_schema_version=INDEX_SCHEMA_VERSION + 1))

    assert result["rebuild_required"] is True


def test_an_unknown_digest_on_either_side_is_not_a_mismatch():
    # An index built while Ollama was unreachable has no digest; forcing a
    # rebuild for that would be worse than proceeding.
    assert compare(fp(embedding_digest=None), fp())["rebuild_required"] is False
    assert compare(fp(), fp(embedding_digest=None))["rebuild_required"] is False


def test_chunker_change_is_advisory_not_a_rebuild():
    # Existing vectors stay valid; only future chunking differs.
    result = compare(fp(), fp(chunker_version="recursive-char-v2"))

    assert result["rebuild_required"] is False
    assert result["status"] == "advisory"
    assert result["advisory_changed"] == ["chunker_version"]


def test_parser_change_is_advisory():
    result = compare(fp(), fp(parser_version="local-parser-v2"))

    assert result["status"] == "advisory"
    assert result["rebuild_required"] is False


def test_rebuild_takes_precedence_over_advisory():
    result = compare(fp(), fp(embedding_model="other", chunker_version="recursive-char-v2"))

    assert result["status"] == "mismatch"
    assert result["rebuild_required"] is True
