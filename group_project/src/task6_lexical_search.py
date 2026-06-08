"""Task 6 - Lexical BM25 search for the group local index."""

from __future__ import annotations

import numpy as np

from group_project.src._index_store import get_bm25_state, tokenize


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    state = get_bm25_state()
    chunks = state["chunks"]
    if not chunks or not query.strip():
        return []

    scores = state["bm25"].get_scores(tokenize(query))
    top_indices = np.argsort(scores)[::-1][: min(top_k, len(chunks))]

    results: list[dict] = []
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
                "retriever": "lexical",
            }
        )
    return results


if __name__ == "__main__":
    for item in lexical_search("luat phong chong ma tuy", top_k=3):
        print(f"{item['score']:.3f} {item['metadata'].get('source')}")

