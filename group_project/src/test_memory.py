"""
Test suite cho tầng conversation memory (group_project/src/conversation_memory.py).

Chạy:
    pytest group_project/src/test_memory.py -v

Test KHÔNG cần OPENAI_API_KEY và KHÔNG cần index Task 4:
    - ChatHistoryStore chạy trên SQLite :memory:
    - condense_question test ở nhánh fallback / fake client
    - ConversationMemory.chat monkeypatch retrieve_chunks + generate_with_history
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

# Cho phép import conversation_memory (cùng thư mục) + src.* (repo root)
SRC_DIR = Path(__file__).resolve().parent          # group_project/src
REPO_ROOT = SRC_DIR.parents[1]                       # repo root
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import conversation_memory as cm
except ImportError as e:  # pragma: no cover
    cm = None
    _IMPORT_ERROR = e


# ---------------------------------------------------------------------------
# Fake OpenAI client (mô phỏng client.chat.completions.create(...).choices[0].message.content)
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, content: str):
        self._content = content
        outer = self

        class _Completions:
            def create(self, **kwargs):
                msg = type("M", (), {"content": outer._content})()
                choice = type("C", (), {"message": msg})()
                return type("R", (), {"choices": [choice]})()

        self.chat = type("Chat", (), {"completions": _Completions()})()


def _skip_if_no_module(test):
    if cm is None:
        test.skipTest(f"Không import được conversation_memory: {_IMPORT_ERROR}")


# ---------------------------------------------------------------------------
# ChatHistoryStore
# ---------------------------------------------------------------------------

class TestChatHistoryStore(unittest.TestCase):
    def setUp(self):
        _skip_if_no_module(self)
        self.store = cm.ChatHistoryStore(db_path=":memory:")

    def tearDown(self):
        if cm is not None:
            self.store.close()

    def test_add_and_get_history_in_order(self):
        sid = self.store.create_session("t")
        self.store.add_message(sid, "user", "câu 1")
        self.store.add_message(sid, "assistant", "trả lời 1")
        history = self.store.get_history(sid)
        self.assertEqual(len(history), 2)
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])
        self.assertEqual(history[0]["content"], "câu 1")

    def test_sources_roundtrip_json(self):
        sid = self.store.create_session()
        chunks = [{"content": "c", "score": 0.9, "source": "hybrid", "metadata": {"source": "doc"}}]
        self.store.add_message(sid, "assistant", "ans", sources=chunks, rewritten_query="q*")
        msg = self.store.get_history(sid)[-1]
        self.assertEqual(msg["sources"], chunks)          # JSON roundtrip giữ nguyên
        self.assertEqual(msg["rewritten_query"], "q*")

    def test_limit_returns_most_recent_chronological(self):
        sid = self.store.create_session()
        for i in range(5):
            self.store.add_message(sid, "user", f"m{i}")
        recent = self.store.get_history(sid, limit=2)
        self.assertEqual([m["content"] for m in recent], ["m3", "m4"])  # gần nhất, đúng thứ tự

    def test_clear_session(self):
        sid = self.store.create_session()
        self.store.add_message(sid, "user", "x")
        self.store.clear_session(sid)
        self.assertEqual(self.store.get_history(sid), [])

    def test_add_message_auto_creates_session(self):
        # add_message với session_id chưa tồn tại không được crash
        self.store.add_message("ghost-session", "user", "hi")
        self.assertEqual(len(self.store.get_history("ghost-session")), 1)


# ---------------------------------------------------------------------------
# condense_question
# ---------------------------------------------------------------------------

class TestCondenseQuestion(unittest.TestCase):
    def setUp(self):
        _skip_if_no_module(self)

    def test_empty_history_returns_question_unchanged(self):
        self.assertEqual(cm.condense_question([], "Câu hỏi gốc?"), "Câu hỏi gốc?")

    def test_no_client_returns_question_unchanged(self):
        history = [{"role": "user", "content": "Hình phạt tàng trữ ma tuý?"}]
        with mock.patch.object(cm, "_get_openai_client", return_value=None):
            self.assertEqual(cm.condense_question(history, "còn mức cao nhất?"), "còn mức cao nhất?")

    def test_with_client_returns_rewritten(self):
        history = [{"role": "user", "content": "Hình phạt tàng trữ ma tuý?"}]
        fake = _FakeClient("Mức hình phạt cao nhất cho tội tàng trữ trái phép chất ma tuý là gì?")
        out = cm.condense_question(history, "còn mức cao nhất?", client=fake)
        self.assertIn("cao nhất", out)
        self.assertNotEqual(out, "còn mức cao nhất?")

    def test_client_error_falls_back_to_question(self):
        history = [{"role": "user", "content": "abc"}]

        class _BoomClient:
            class chat:  # noqa: N801
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        raise RuntimeError("API down")

        self.assertEqual(cm.condense_question(history, "follow?", client=_BoomClient()), "follow?")


# ---------------------------------------------------------------------------
# ConversationMemory.chat  (monkeypatch retrieve + generation)
# ---------------------------------------------------------------------------

class TestConversationMemoryChat(unittest.TestCase):
    def setUp(self):
        _skip_if_no_module(self)
        self.store = cm.ChatHistoryStore(db_path=":memory:")
        self.memory = cm.ConversationMemory(store=self.store, top_k=3)

        self.fake_chunks = [
            {"content": "Điều 249...", "score": 0.88, "source": "hybrid",
             "metadata": {"source": "luat-phong-chong-ma-tuy.md", "type": "legal"}},
        ]
        # Patch retrieval + generation để khỏi cần ML stack / API / index
        self._patchers = [
            mock.patch.object(cm, "retrieve_chunks", return_value=self.fake_chunks),
            mock.patch.object(cm, "generate_with_history", return_value="CÂU TRẢ LỜI [nguồn]"),
        ]
        self.mocks = [p.start() for p in self._patchers]

    def tearDown(self):
        if cm is None:
            return
        for p in self._patchers:
            p.stop()
        self.store.close()

    def test_chat_returns_expected_shape(self):
        sid = self.memory.new_session()
        result = self.memory.chat(sid, "Hình phạt tàng trữ ma tuý?")
        for key in ("answer", "sources", "rewritten_query", "original_query",
                    "retrieval_source", "session_id"):
            self.assertIn(key, result)
        self.assertEqual(result["answer"], "CÂU TRẢ LỜI [nguồn]")
        self.assertEqual(result["sources"], self.fake_chunks)
        self.assertEqual(result["retrieval_source"], "hybrid")
        self.assertEqual(result["original_query"], "Hình phạt tàng trữ ma tuý?")

    def test_chat_persists_user_and_assistant(self):
        sid = self.memory.new_session()
        self.memory.chat(sid, "câu hỏi 1")
        history = self.store.get_history(sid)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["sources"], self.fake_chunks)

    def test_followup_passes_prior_history_to_condense(self):
        sid = self.memory.new_session()
        self.memory.chat(sid, "Hình phạt tàng trữ ma tuý?")
        with mock.patch.object(cm, "condense_question", return_value="standalone") as cond:
            self.memory.chat(sid, "còn mức cao nhất?")
        # Lượt 2: condense phải nhận history KHÔNG rỗng (gồm lượt 1) + câu follow-up gốc
        history_arg, question_arg = cond.call_args.args
        self.assertEqual(question_arg, "còn mức cao nhất?")
        self.assertGreaterEqual(len(history_arg), 2)

    def test_empty_retrieval_gives_source_none(self):
        with mock.patch.object(cm, "retrieve_chunks", return_value=[]):
            sid = self.memory.new_session()
            result = self.memory.chat(sid, "câu hỏi lạ")
        self.assertEqual(result["retrieval_source"], "none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
