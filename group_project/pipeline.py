"""
Pipeline interface chung — contract cho UI, Memory, Evaluation (Lead).

Mọi module nhóm NÊN import từ file này thay vì gọi trực tiếp nhiều task rời rạc.

Ví dụ:
    from group_project.pipeline import rag_query, rag_retrieve, chat_turn

    result = rag_query("Hình phạt tàng trữ ma tuý?")
    answer = result["answer"]
    sources = result["sources"]
"""

from __future__ import annotations

from group_project.src.conversation_memory import ConversationMemory
from group_project.src.task10_generation import answer_question
from group_project.src.task9_retrieval_pipeline import retrieve

__all__ = [
    "RAGResult",
    "ChatResult",
    "rag_query",
    "rag_retrieve",
    "chat_turn",
    "ConversationMemory",
]

# Type aliases (documented contract)
RAGResult = dict  # answer, sources, context, retrieval_source, policy
ChatResult = dict  # answer, sources, rewritten_query, original_query, retrieval_source, session_id


def rag_retrieve(query: str, top_k: int = 5, **retrieve_kwargs) -> list[dict]:
    """Truy xuất chunks — dùng cho debug hoặc eval retrieval-only."""
    return retrieve(query, top_k=top_k, **retrieve_kwargs)


def rag_query(question: str, top_k: int = 5, **retrieve_kwargs) -> RAGResult:
    """
    Hỏi đáp một lượt (không memory).

    Returns:
        {
            "answer": str,
            "sources": list[dict],      # formatted for UI
            "context": str,
            "retrieval_source": str,    # hybrid | pageindex | none
            "policy": str,
        }
    """
    if retrieve_kwargs:
        chunks = retrieve(question, top_k=top_k, **retrieve_kwargs)
        from group_project.src.task10_generation import (
            format_context,
            format_sources,
            has_enough_evidence,
            select_evidence,
        )

        context = format_context(chunks)
        sources = format_sources(chunks)
        retrieval_source = chunks[0].get("source", "none") if chunks else "none"
        if not has_enough_evidence(chunks):
            answer = (
                "Tôi không thể xác minh thông tin này từ các nguồn hiện có. "
                "Các đoạn truy xuất được không đủ liên quan để đưa ra câu trả lời có căn cứ."
            )
        else:
            evidence = select_evidence(question, chunks)
            if not evidence:
                answer = (
                    "Tôi không thể xác minh thông tin này từ các nguồn hiện có. "
                    "Không có câu hoặc đoạn đủ rõ để trích dẫn."
                )
            else:
                lines = ["Dựa trên các nguồn đã truy xuất, câu trả lời có căn cứ như sau:"]
                for item in evidence:
                    lines.append(f"- {item['sentence']} [{item['label']}]")
                lines.append(
                    "Tôi chỉ sử dụng các đoạn được truy xuất ở trên; nếu cần kết luận pháp lý chính thức, "
                    "hãy đối chiếu trực tiếp văn bản gốc."
                )
                answer = "\n".join(lines)
        from group_project.src.task10_generation import ANTI_HALLUCINATION_POLICY

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
            "retrieval_source": retrieval_source,
            "policy": ANTI_HALLUCINATION_POLICY,
        }
    return answer_question(question, top_k=top_k)


def chat_turn(
    memory: ConversationMemory,
    session_id: str,
    user_message: str,
) -> ChatResult:
    """Một lượt hội thoại có memory (follow-up)."""
    return memory.chat(session_id, user_message)
