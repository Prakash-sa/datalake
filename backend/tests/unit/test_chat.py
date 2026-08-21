"""Conversation turns: history, follow-ups, and persistence."""

from __future__ import annotations

import pytest

from rag_backend.application.chat_service import ChatService, derive_title
from rag_backend.application.prompts import build_retrieval_query, render_history
from rag_backend.application.rag_service import DocumentRAGService


class StubEmbeddings:
    dimensions = 8

    def embed_query(self, content: str) -> list[float]:
        return [float(len(content) % 5)] * 8


class StubGeneration:
    """Generation provider surface only."""

    name = "test"
    model_name = "test-model"

    def __init__(self, tokens: list[str] | None = None):
        self.tokens = tokens or ["Merged ", "with ", "RRF ", "[S1]."]
        self.prompts: list[str] = []

    def stream_generate(self, prompt, temperature=0.1, cancel=None, **kwargs):
        self.prompts.append(prompt)
        for token in self.tokens:
            if cancel is not None and cancel.is_set():
                return
            yield token

    def generate(self, prompt, temperature=0.1):
        return "".join(self.stream_generate(prompt, temperature=temperature))

    def health(self):
        return {"status": "ready", "provider": self.name, "model": self.model_name}


@pytest.fixture
def rag(tmp_path) -> DocumentRAGService:
    service = DocumentRAGService(
        chroma_path=str(tmp_path / "chroma"), app_db_path=str(tmp_path / "app.db")
    )
    service.embeddings = StubEmbeddings()
    service.generation = StubGeneration()
    service.index_documents(
        [{"id": "chunk-1", "content": "rankings merged with fusion", "metadata": {}}]
    )
    return service


@pytest.fixture
def chat(rag) -> ChatService:
    return ChatService(rag)


def _run(chat: ChatService, message: str, conversation_id: str | None = None):
    return list(chat.stream_turn(message, conversation_id=conversation_id))


class TestTitles:
    def test_a_short_question_becomes_the_title(self):
        assert derive_title("How are rankings merged?") == "How are rankings merged?"

    def test_a_long_question_is_truncated(self):
        title = derive_title("word " * 60)
        assert len(title) <= 60
        assert title.endswith("…")

    def test_an_empty_question_still_yields_a_title(self):
        assert derive_title("   ") == "New conversation"


class TestHistory:
    def test_history_is_empty_for_a_new_conversation(self):
        assert render_history([]) == ""

    def test_history_includes_both_roles(self):
        rendered = render_history(
            [
                {"role": "user", "content": "How are rankings merged?"},
                {"role": "assistant", "content": "With fusion."},
            ]
        )
        assert "User: How are rankings merged?" in rendered
        assert "Assistant: With fusion." in rendered

    def test_only_recent_turns_are_carried(self):
        messages = [{"role": "user", "content": f"q{i}"} for i in range(20)]
        rendered = render_history(messages)

        # Older turns must not crowd out the retrieved evidence.
        assert "q19" in rendered
        assert "q0" not in rendered


class TestFollowUps:
    @pytest.mark.parametrize(
        "question",
        ["what about the second one?", "why is that?", "and the embedding model?", "tell me more"],
    )
    def test_a_follow_up_is_expanded_with_the_previous_question(self, question):
        history = [{"role": "user", "content": "How are rankings merged?"}]

        assert build_retrieval_query(question, history).startswith("How are rankings merged?")

    @pytest.mark.parametrize(
        "question",
        [
            "Explain in detail how privacy is preserved across the whole pipeline",
            "Which documents describe the ingestion job state machine and its transitions?",
            "How does the chunker decide where to split a long document?",
        ],
    )
    def test_a_self_contained_question_is_left_alone(self, question):
        # Prepending history would pull retrieval back to the earlier topic.
        history = [{"role": "user", "content": "How are rankings merged?"}]

        assert build_retrieval_query(question, history) == question

    def test_nothing_to_expand_with_on_the_first_turn(self):
        assert build_retrieval_query("why is that?", []) == "why is that?"


class TestTurns:
    def test_a_turn_announces_its_conversation_first(self, chat):
        events = _run(chat, "How are rankings merged?")

        assert events[0]["event"] == "conversation"
        assert events[0]["conversation_id"].startswith("conv_")
        assert events[0]["title"] == "How are rankings merged?"

    def test_a_turn_streams_sources_then_tokens_then_done(self, chat):
        events = [e["event"] for e in _run(chat, "How are rankings merged?")]

        assert events[0] == "conversation"
        assert events[1] == "sources"
        assert "token" in events
        assert events[-1] == "done"

    def test_the_answer_is_persisted_with_its_citations(self, chat):
        done = _run(chat, "How are rankings merged?")[-1]

        conversation = chat.get_conversation(done["conversation_id"])
        roles = [m["role"] for m in conversation["messages"]]
        assert roles == ["user", "assistant"]
        assert conversation["messages"][1]["content"] == "Merged with RRF [S1]."
        assert conversation["messages"][1]["citations"]["valid"] is True

    def test_a_second_turn_continues_the_same_conversation(self, chat):
        first = _run(chat, "How are rankings merged?")[-1]
        second = _run(chat, "why is that?", conversation_id=first["conversation_id"])[-1]

        assert second["conversation_id"] == first["conversation_id"]
        conversation = chat.get_conversation(first["conversation_id"])
        assert len(conversation["messages"]) == 4

    def test_the_second_turn_sees_the_first_in_its_prompt(self, chat, rag):
        first = _run(chat, "How are rankings merged?")[-1]
        _run(chat, "why is that?", conversation_id=first["conversation_id"])

        assert "CONVERSATION SO FAR" in rag.generation.prompts[-1]
        assert "How are rankings merged?" in rag.generation.prompts[-1]

    def test_the_question_survives_a_cancelled_turn(self, chat):
        import threading

        cancel = threading.Event()
        cancel.set()
        events = list(chat.stream_turn("How are rankings merged?", cancel=cancel))

        conversation = chat.get_conversation(events[0]["conversation_id"])
        assert conversation["messages"][0]["content"] == "How are rankings merged?"
        assert events[-1]["event"] == "error"


class TestConversationManagement:
    def test_conversations_are_listed_newest_first(self, chat):
        _run(chat, "First question about rankings")
        _run(chat, "Second question about privacy")

        titles = [c["title"] for c in chat.list_conversations()]
        assert titles[0] == "Second question about privacy"

    def test_a_conversation_can_be_renamed(self, chat):
        done = _run(chat, "How are rankings merged?")[-1]

        assert chat.rename_conversation(done["conversation_id"], "Retrieval notes") is True
        assert chat.get_conversation(done["conversation_id"])["title"] == "Retrieval notes"

    def test_deleting_a_conversation_removes_its_messages(self, chat):
        done = _run(chat, "How are rankings merged?")[-1]

        assert chat.delete_conversation(done["conversation_id"]) is True
        assert chat.get_conversation(done["conversation_id"]) is None

    def test_renaming_or_deleting_an_unknown_conversation_reports_failure(self, chat):
        assert chat.rename_conversation("conv_missing", "x") is False
        assert chat.delete_conversation("conv_missing") is False
