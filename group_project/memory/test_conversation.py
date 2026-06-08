"""Unit test cho tầng conversation memory.

Chạy:
    python -m pytest group_project/memory/test_conversation.py -v
hoặc:
    python group_project/memory/test_conversation.py

Test phần thuần logic (không gọi LLM) để chạy được offline, không cần API key.
"""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from conversation import (
    _fallback_contextual_query,
    _recent_history_text,
    build_contextual_query,
)


class TestBuildContextualQuery(unittest.TestCase):
    def test_empty_history_returns_question_unchanged(self):
        """Lượt đầu (chưa có lịch sử) -> giữ nguyên câu hỏi."""
        self.assertEqual(
            build_contextual_query("Hình phạt tàng trữ ma tuý là gì?", []),
            "Hình phạt tàng trữ ma tuý là gì?",
        )

    def test_strips_whitespace(self):
        self.assertEqual(build_contextual_query("  ai quyết định?  ", []), "ai quyết định?")

    def test_none_question_safe(self):
        self.assertEqual(build_contextual_query(None, []), "")


class TestRecentHistoryText(unittest.TestCase):
    def test_window_keeps_only_recent_turns(self):
        msgs = [{"role": "user", "content": f"q{i}"} for i in range(10)]
        text = _recent_history_text(msgs, max_turns=2)  # giữ 4 message cuối
        self.assertIn("q9", text)
        self.assertIn("q6", text)
        self.assertNotIn("q5", text)

    def test_skips_empty_content(self):
        msgs = [{"role": "user", "content": ""}, {"role": "assistant", "content": "Có nội dung"}]
        text = _recent_history_text(msgs)
        self.assertIn("Có nội dung", text)
        self.assertNotIn("Người dùng:", text)

    def test_labels_roles_in_vietnamese(self):
        msgs = [
            {"role": "user", "content": "câu hỏi"},
            {"role": "assistant", "content": "trả lời"},
        ]
        text = _recent_history_text(msgs)
        self.assertIn("Người dùng: câu hỏi", text)
        self.assertIn("Trợ lý: trả lời", text)


class TestFallbackContextualQuery(unittest.TestCase):
    def test_contains_history_and_new_question(self):
        history = _recent_history_text(
            [
                {"role": "user", "content": "Miu Lê bị bắt vì gì?"},
                {"role": "assistant", "content": "Vì liên quan ma tuý."},
            ]
        )
        query = _fallback_contextual_query(history, "Cô ấy bị bắt ở đâu?")
        self.assertIn("Miu Lê", query)
        self.assertIn("Cô ấy bị bắt ở đâu?", query)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main(verbosity=2)
