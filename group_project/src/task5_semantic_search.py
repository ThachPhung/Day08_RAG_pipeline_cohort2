"""Task 5 - Semantic search over the group local vector index."""

from __future__ import annotations

import numpy as np

from group_project.src._index_store import cosine_similarity, embed_query, ensure_index


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    chunks = ensure_index()
    if not chunks or not query.strip():
        return []

    query_vector = embed_query(query)
    matrix = np.asarray([chunk["embedding"] for chunk in chunks], dtype=np.float32)
    scores = cosine_similarity(query_vector, matrix)
    top_indices = np.argsort(scores)[::-1][: min(top_k, len(chunks))]

    return [
        {
            "content": chunks[int(idx)]["content"],
            "score": float(scores[idx]),
            "metadata": chunks[int(idx)].get("metadata", {}),
            "retriever": "semantic",
        }
        for idx in top_indices
    ]


if __name__ == "__main__":
    for item in semantic_search("hinh phat ma tuy", top_k=3):
        print(f"{item['score']:.3f} {item['metadata'].get('source')}")

