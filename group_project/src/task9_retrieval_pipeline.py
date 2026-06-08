"""Task 9 - Complete retrieval pipeline for the group project."""

from __future__ import annotations

from group_project.src.task5_semantic_search import semantic_search
from group_project.src.task6_lexical_search import lexical_search
from group_project.src.task7_reranking import rerank, rerank_rrf
from group_project.src.task8_pageindex_vectorless import pageindex_search

DEFAULT_TOP_K = 5
SCORE_THRESHOLD = 0.3


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_semantic: bool = True,
    use_lexical: bool = True,
    use_reranking: bool = True,
) -> list[dict]:
    """Run semantic + lexical retrieval, fuse, rerank, then fallback if weak."""
    fetch_k = max(top_k * 3, 10)
    ranked_lists: list[list[dict]] = []

    if use_semantic:
        ranked_lists.append(semantic_search(query, top_k=fetch_k))
    if use_lexical:
        ranked_lists.append(lexical_search(query, top_k=fetch_k))

    ranked_lists = [items for items in ranked_lists if items]
    if not ranked_lists:
        return pageindex_search(query, top_k=top_k)

    merged = rerank_rrf(ranked_lists, top_k=fetch_k)
    for item in merged:
        item["source"] = "hybrid"

    final = rerank(query, merged, top_k=top_k) if use_reranking else merged[:top_k]
    for item in final:
        item["source"] = "hybrid"

    if not final or float(final[0].get("score", 0.0)) < score_threshold:
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            return fallback[:top_k]

    return final[:top_k]


if __name__ == "__main__":
    for result in retrieve("Luật phòng chống ma túy quy định gì?", top_k=3):
        print(f"{result['score']:.3f} [{result['source']}] {result['metadata'].get('source')}")

