"""Choosing a generation model from what is installed."""

from __future__ import annotations

import pytest

from rag_backend.domain.model_selection import (
    generation_candidates,
    is_embedding_model,
    select_generation_model,
)


class TestEmbeddingDetection:
    @pytest.mark.parametrize(
        "name",
        [
            "qwen3-embedding:0.6b",
            "nomic-embed-text",
            "mxbai-embed-large",
            "all-minilm:l6-v2",
            "bge-small",
        ],
    )
    def test_embedding_models_are_recognised(self, name):
        # Selecting one of these would fail confusingly at query time.
        assert is_embedding_model(name) is True

    @pytest.mark.parametrize("name", ["qwen3:4b", "llama3.1:8b", "mistral", "phi4"])
    def test_generation_models_are_not(self, name):
        assert is_embedding_model(name) is False


class TestCandidates:
    def test_embedding_models_are_excluded(self):
        assert generation_candidates(["qwen3-embedding:0.6b", "qwen3:4b"]) == ["qwen3:4b"]

    def test_known_families_are_preferred_over_unknown(self):
        ordered = generation_candidates(["zzz-custom:1b", "llama3:8b"])

        assert ordered[0] == "llama3:8b"

    def test_smaller_known_size_is_preferred_within_a_family(self):
        ordered = generation_candidates(
            ["qwen3.5:latest", "qwen3:1.7b"],
            {"qwen3.5:latest": 6_600_000_000, "qwen3:1.7b": 1_400_000_000},
        )

        assert ordered == ["qwen3:1.7b", "qwen3.5:latest"]

    def test_unknown_size_sorts_after_known_size(self):
        ordered = generation_candidates(["qwen3.5:latest", "qwen3:1.7b"], {"qwen3:1.7b": 1})

        assert ordered == ["qwen3:1.7b", "qwen3.5:latest"]

    def test_an_unknown_family_is_still_usable(self):
        assert generation_candidates(["zzz-custom:1b"]) == ["zzz-custom:1b"]


class TestSelection:
    def test_the_configured_model_wins_when_installed(self):
        chosen, reason = select_generation_model(["qwen3:4b", "llama3:8b"], "qwen3:4b")

        assert (chosen, reason) == ("qwen3:4b", "configured")

    def test_a_different_tag_of_the_configured_family_is_accepted(self):
        chosen, reason = select_generation_model(["qwen3:1.7b"], "qwen3:4b")

        assert chosen == "qwen3:1.7b"
        assert reason == "configured-family"

    def test_configured_family_uses_the_smallest_installed_tag_when_sizes_are_known(self):
        chosen, reason = select_generation_model(
            ["qwen3.5:latest", "qwen3:1.7b"],
            "qwen3:4b",
            {"qwen3.5:latest": 6_600_000_000, "qwen3:1.7b": 1_400_000_000},
        )

        assert chosen == "qwen3:1.7b"
        assert reason == "configured-family"

    def test_an_installed_model_is_used_when_the_configured_one_is_absent(self):
        # This is the case that produced a 404 on every query.
        chosen, reason = select_generation_model(
            ["qwen3-embedding:0.6b", "qwen3.5:latest"], "qwen3:4b"
        )

        assert chosen == "qwen3.5:latest"
        assert reason == "auto-selected"

    def test_nothing_usable_returns_none(self):
        chosen, reason = select_generation_model(["qwen3-embedding:0.6b"], "qwen3:4b")

        assert chosen is None
        assert reason == "none-installed"

    def test_empty_ollama_returns_none(self):
        assert select_generation_model([], "qwen3:4b") == (None, "none-installed")

    def test_a_model_is_chosen_when_nothing_is_configured(self):
        chosen, reason = select_generation_model(["mistral:7b"], None)

        assert chosen == "mistral:7b"
        assert reason == "auto-selected-default"

    def test_small_model_is_chosen_when_nothing_is_configured(self):
        chosen, reason = select_generation_model(
            ["qwen3.5:latest", "qwen3:1.7b"],
            None,
            {"qwen3.5:latest": 6_600_000_000, "qwen3:1.7b": 1_400_000_000},
        )

        assert chosen == "qwen3:1.7b"
        assert reason == "auto-selected-default"
