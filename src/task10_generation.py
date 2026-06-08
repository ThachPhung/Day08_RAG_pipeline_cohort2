"""
Task 10 — Generation Có Citation.

Triển khai local extractive generation để chạy được khi chưa có API key. Pipeline
vẫn gồm retrieve -> reorder -> format context -> answer with citation.
"""

from __future__ import annotations

from .rag_utils import summarize_text
from .task9_retrieval_pipeline import retrieve


TOP_K = 5  # đủ evidence, không làm context quá dài
TOP_P = 0.9  # dùng khi thay bằng LLM thật
TEMPERATURE = 0.3  # factual RAG nên giữ thấp


SYSTEM_PROMPT = """Answer the following question comprehensively in Vietnamese.
For every statement of fact or claim, immediately insert a citation in brackets.
If the information is not explicitly stated in the provided context, state
'Tôi không thể xác minh thông tin này từ nguồn hiện có'."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle".

    Pattern với 5 chunks: [1, 3, 5, 4, 2].
    """
    if len(chunks) <= 2:
        return chunks

    front = chunks[::2]
    back = chunks[1::2][::-1]
    return front + back


def format_context(chunks: list[dict]) -> str:
    """Format chunks thành context string có source label để cite."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", f"Source {i}")
        doc_type = metadata.get("type", "unknown")
        score = chunk.get("score", 0.0)
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type} | Score: {score:.3f}]\n"
            f"{chunk.get('content', '')}"
        )
    return "\n\n---\n\n".join(context_parts)


def _citation_for(chunk: dict) -> str:
    metadata = chunk.get("metadata", {})
    source = metadata.get("source", "Nguồn không rõ").replace(".md", "")
    return f"[{source}]"


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.

    Returns:
        {'answer': str, 'sources': list[dict], 'retrieval_source': str}
    """
    chunks = retrieve(query, top_k=top_k)
    reordered = reorder_for_llm(chunks)
    _ = format_context(reordered)

    if not reordered:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": [],
            "retrieval_source": "none",
        }

    answer_parts = []
    for chunk in reordered[: min(3, len(reordered))]:
        snippet = summarize_text(chunk.get("content", ""), max_chars=320)
        answer_parts.append(f"{snippet} {_citation_for(chunk)}")

    answer = (
        "Dựa trên các nguồn đã truy xuất, thông tin liên quan là: "
        + " ".join(answer_parts)
    )

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none",
    }


if __name__ == "__main__":
    result = generate_with_citation(
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?"
    )
    print(result["answer"])
