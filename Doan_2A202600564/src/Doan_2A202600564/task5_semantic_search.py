"""
Task 5 — Semantic Search Module.
"""

import numpy as np

from src._index_store import cosine_similarity, embed_query, ensure_index


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng cosine similarity trên local index.
    """
    chunks = ensure_index()
    if not chunks:
        return []

    query_vec = embed_query(query)
    matrix = np.asarray([c["embedding"] for c in chunks], dtype=np.float32)
    scores = cosine_similarity(query_vec, matrix)

    top_k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        chunk = chunks[int(idx)]
        results.append(
            {
                "content": chunk["content"],
                "score": float(scores[idx]),
                "metadata": chunk.get("metadata", {}),
            }
        )
    return results


if __name__ == "__main__":
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
