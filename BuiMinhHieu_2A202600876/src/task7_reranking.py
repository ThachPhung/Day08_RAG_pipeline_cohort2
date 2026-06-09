"""Task 7 - Reranking module."""

try:
    from .local_rag_utils import simple_embedding, cosine_similarity, tokenize
except ImportError:
    from local_rag_utils import simple_embedding, cosine_similarity, tokenize


def _keyword_overlap(query: str, content: str) -> float:
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    content_terms = set(tokenize(content))
    return len(query_terms & content_terms) / len(query_terms)


def rerank_cross_encoder(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Offline cross-encoder substitute based on overlap + original score."""
    reranked = []
    for candidate in candidates:
        original = float(candidate.get("score", 0.0))
        overlap = _keyword_overlap(query, candidate.get("content", ""))
        score = 0.6 * original + 0.4 * overlap
        reranked.append({**candidate, "score": float(score)})
    reranked.sort(key=lambda item: item["score"], reverse=True)
    return reranked[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    selected: list[int] = []
    remaining = list(range(len(candidates)))
    embeddings = [
        candidate.get("embedding") or simple_embedding(candidate.get("content", ""))
        for candidate in candidates
    ]

    while remaining and len(selected) < top_k:
        best_idx = remaining[0]
        best_score = float("-inf")
        for idx in remaining:
            relevance = cosine_similarity(query_embedding, embeddings[idx])
            diversity_penalty = max(
                (cosine_similarity(embeddings[idx], embeddings[sel]) for sel in selected),
                default=0.0,
            )
            score = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
            if score > best_score:
                best_idx = idx
                best_score = score
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [{**candidates[idx], "score": float(candidates[idx].get("score", 0.0))} for idx in selected]


def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item.get("content", "")
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items[key] = item

    merged = []
    for content, score in sorted(scores.items(), key=lambda pair: pair[1], reverse=True):
        merged.append({**items[content], "score": float(score)})
    return merged[:top_k]


def rerank(query: str, candidates: list[dict], top_k: int = 5, method: str = "cross_encoder") -> list[dict]:
    if method == "mmr":
        return rerank_mmr(simple_embedding(query), candidates, top_k=top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k=top_k)
    return rerank_cross_encoder(query, candidates, top_k=top_k)


if __name__ == "__main__":
    docs = [
        {"content": "Toi tang tru trai phep chat ma tuy", "score": 0.8, "metadata": {}},
        {"content": "Python programming", "score": 0.5, "metadata": {}},
    ]
    print(rerank("hinh phat ma tuy", docs, top_k=2))
