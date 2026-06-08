"""Conversation memory — biến câu hỏi follow-up thành câu hỏi độc lập.

Khi người dùng hỏi nối tiếp ("còn dưới 18 tuổi thì sao?", "ai quyết định?"),
câu hỏi thiếu ngữ cảnh nên retrieve sẽ sai. Module này dùng lịch sử chat để
viết lại thành MỘT câu hỏi đầy đủ ngữ cảnh trước khi đưa vào pipeline RAG.

API công khai (theo spec của lead):
    build_contextual_query(user_question, messages, max_turns=3) -> str

`messages` là list lịch sử kiểu Streamlit mà lead quy định:
    {"role": "user", "content": "..."}
    {"role": "assistant", "content": "...", "sources": [...]}

Chất lượng: nếu có OPENAI_API_KEY -> dùng LLM condense (câu standalone sạch,
retrieve chính xác hơn). Không có key -> fallback nối ngữ cảnh (vẫn chạy được).
Không phụ thuộc Streamlit nên test/độc lập được.
"""

from __future__ import annotations

import os

MAX_TURNS = 3

CONDENSE_SYSTEM_PROMPT = (
    "Bạn là trợ lý viết lại câu hỏi cho hệ thống tìm kiếm. "
    "Cho lịch sử hội thoại và một câu hỏi mới (thường là câu follow-up ngắn, có "
    "đại từ hoặc thiếu ngữ cảnh), hãy viết lại thành MỘT câu hỏi độc lập, đầy đủ "
    "ngữ cảnh, giữ đúng ý định người dùng và bằng tiếng Việt. "
    "Chỉ trả về câu hỏi đã viết lại, không thêm giải thích. "
    "Nếu câu hỏi mới đã đầy đủ ngữ cảnh thì trả về gần như nguyên văn."
)


def _recent_history_text(messages: list[dict], max_turns: int = MAX_TURNS) -> str:
    """Ghép N lượt gần nhất thành text. max_turns lượt ~ max_turns*2 message."""
    recent = messages[-max_turns * 2:] if max_turns > 0 else list(messages)
    lines = []
    for m in recent:
        role = "Người dùng" if m.get("role") == "user" else "Trợ lý"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _fallback_contextual_query(history_text: str, user_question: str) -> str:
    """Fallback không cần LLM (đúng kiểu nối chuỗi trong ví dụ của lead)."""
    return (
        f"Dựa trên hội thoại trước:\n{history_text}\n\n"
        f"Câu hỏi mới: {user_question}\n"
        "Hãy hiểu câu hỏi mới theo ngữ cảnh hội thoại trên."
    )


def _condense_with_llm(history_text: str, user_question: str) -> str | None:
    """Viết lại follow-up thành câu standalone bằng OpenAI. None nếu không khả dụng."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-xxx"):
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        user_msg = (
            f"Lịch sử hội thoại:\n{history_text}\n\n"
            f"Câu hỏi mới: {user_question}\n\n"
            "Câu hỏi độc lập:"
        )
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        return rewritten or None
    except Exception:
        # Lỗi mạng/quota/API -> degrade về fallback, không làm sập app
        return None


def build_contextual_query(
    user_question: str,
    messages: list[dict],
    max_turns: int = MAX_TURNS,
) -> str:
    """Tạo câu hỏi đầy đủ ngữ cảnh từ câu follow-up + lịch sử chat.

    - Chưa có lịch sử -> trả câu hỏi như cũ (lượt đầu không cần ghép gì).
    - Có lịch sử -> LLM viết lại thành câu standalone (chất lượng cao);
      nếu LLM không khả dụng -> nối ngữ cảnh kiểu fallback.
    """
    user_question = (user_question or "").strip()
    if not messages:
        return user_question

    history_text = _recent_history_text(messages, max_turns)
    if not history_text:
        return user_question

    rewritten = _condense_with_llm(history_text, user_question)
    if rewritten:
        return rewritten
    return _fallback_contextual_query(history_text, user_question)


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    demo_messages = [
        {"role": "user", "content": "Ca sĩ Miu Lê bị bắt vì lý do gì?"},
        {"role": "assistant", "content": "Vì cáo buộc tổ chức sử dụng trái phép chất ma tuý."},
    ]
    for follow_up in ["Cô ấy bị bắt ở đâu?", "Còn ai khác liên quan không?"]:
        print("=" * 60)
        print("Follow-up :", follow_up)
        print("Standalone:", build_contextual_query(follow_up, demo_messages))
