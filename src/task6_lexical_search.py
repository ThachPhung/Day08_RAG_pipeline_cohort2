"""
Task 6 — Lexical Search Module (BM25).
"""

import numpy as np

from src._index_store import get_bm25_state, tokenize


def build_bm25_index(corpus: list[dict]):
    """Xây dựng BM25 index từ corpus (dùng khi rebuild thủ công)."""
    from rank_bm25 import BM25Okapi

    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized_corpus)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.
    """
    state = get_bm25_state()
    bm25 = state["bm25"]
    chunks = state["chunks"]
    if not chunks:
        return []

    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    top_k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score <= 0:
            continue
        chunk = chunks[int(idx)]
        results.append(
            {
                "content": chunk["content"],
                "score": score,
                "metadata": chunk.get("metadata", {}),
            }
        )
    return results


if __name__ == "__main__":
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
