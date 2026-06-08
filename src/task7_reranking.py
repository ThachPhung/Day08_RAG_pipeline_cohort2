"""
Task 7 — Reranking Module.

Triển khai local:
    - rerank_rrf: Reciprocal Rank Fusion để gộp semantic + lexical results.
    - rerank: re-score candidates bằng lexical overlap với query kết hợp score gốc.
      Đây là fallback nhẹ thay cho cross-encoder khi chưa có API key/model local.
"""

from __future__ import annotations

from .rag_utils import cosine_counter_score, tokenize


def rerank_cross_encoder(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Fallback cross-encoder-like rerank without external model."""
    query_tokens = tokenize(query)
    results = []
    for candidate in candidates:
        overlap_score = cosine_counter_score(query_tokens, tokenize(candidate.get("content", "")))
        original_score = float(candidate.get("score", 0.0))
        item = candidate.copy()
        item["score"] = 0.7 * overlap_score + 0.3 * original_score
        results.append(item)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """Minimal MMR fallback using existing candidate scores."""
    del query_embedding, lambda_param
    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:top_k]


def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = sum(1 / (k + rank_r(d)))
    """
    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item.get("content", "")
            if not key:
                continue
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1 / (k + rank)
            content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content].copy()
        item["score"] = float(score)
        results.append(item)
    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",
) -> list[dict]:
    """Unified reranking interface."""
    if not candidates:
        return []
    if method in {"cross_encoder", "local"}:
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k=top_k)
    if method == "mmr":
        return rerank_mmr([], candidates, top_k=top_k)
    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    for r in rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2):
        print(f"[{r['score']:.3f}] {r['content']}")
