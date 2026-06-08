"""
Task 5 — Semantic Search Module.

Bản local fallback dùng cosine similarity trên token-count vectors. Trong demo có
thể thay bằng embedding model thật, nhưng interface giữ đúng yêu cầu Task 5.
"""

from __future__ import annotations

from .rag_utils import cosine_counter_score, tokenize
from .task4_chunking_indexing import chunk_documents, load_documents


def _load_chunks() -> list[dict]:
    return chunk_documents(load_documents())


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity local.

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}
        sorted by score descending.
    """
    query_tokens = tokenize(query)
    results = []
    for chunk in _load_chunks():
        score = cosine_counter_score(query_tokens, tokenize(chunk["content"]))
        if score > 0:
            results.append(
                {
                    "content": chunk["content"],
                    "score": float(score),
                    "metadata": chunk.get("metadata", {}),
                }
            )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    for r in semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5):
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
