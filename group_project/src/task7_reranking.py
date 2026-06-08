"""Task 7 - Reranking and reciprocal rank fusion."""

from __future__ import annotations

from group_project.src._index_store import tokenize


def _keyword_score(query: str, text: str) -> float:
    terms = set(tokenize(query))
    if not terms:
        return 0.0
    text_terms = set(tokenize(text))
    return len(terms & text_terms) / len(terms)


def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 10, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            key = item["content"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in items or item.get("score", 0) > items[key].get("score", 0):
                items[key] = item

    fused: list[dict] = []
    for content, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]:
        fused_item = items[content].copy()
        fused_item["score"] = float(score)
        fused.append(fused_item)
    return fused


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Local reranker: combine normalized retrieval score and query-term overlap."""
    if not candidates:
        return []

    max_base = max(float(item.get("score", 0.0)) for item in candidates) or 1.0
    scored: list[dict] = []
    for item in candidates:
        base = float(item.get("score", 0.0)) / max_base
        relevance = _keyword_score(query, item.get("content", ""))
        new_item = item.copy()
        new_item["score"] = 0.55 * relevance + 0.45 * base
        new_item["reranker"] = "keyword_overlap"
        scored.append(new_item)

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    docs = [
        {"content": "Luật phòng chống ma túy", "score": 0.3, "metadata": {}},
        {"content": "Tin giải trí", "score": 0.8, "metadata": {}},
    ]
    print(rerank("phòng chống ma túy", docs))

