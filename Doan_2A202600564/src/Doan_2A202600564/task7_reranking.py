"""
Task 7 — Reranking Module (keyword relevance + RRF).
"""

from __future__ import annotations

import re
from typing import Optional


def _query_terms(query: str) -> set[str]:
    return {t for t in re.split(r"\W+", query.lower()) if len(t) > 1}


def _keyword_score(query: str, text: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for t in terms if t in text_lower)
    return hits / len(terms)


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank bằng keyword overlap + retrieval score (không cần API key).
    """
    scored = []
    for c in candidates:
        relevance = _keyword_score(query, c.get("content", ""))
        base = float(c.get("score", 0.0))
        combined = 0.7 * relevance + 0.3 * min(base, 1.0)
        item = {**c, "score": combined}
        scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """Maximal Marginal Relevance."""
    import numpy as np

    if not candidates:
        return []

    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)

    q = np.asarray(query_embedding, dtype=np.float32)
    selected: list[int] = []
    remaining = list(range(len(candidates)))

    while remaining and len(selected) < top_k:
        best_idx = None
        best_score = float("-inf")

        for idx in remaining:
            emb = np.asarray(
                candidates[idx].get("embedding", candidates[idx].get("score", 0)),
                dtype=np.float32,
            )
            if emb.ndim == 0:
                relevance = float(candidates[idx].get("score", 0.0))
            else:
                relevance = cosine(q, emb)

            max_sim = 0.0
            for sel_idx in selected:
                sel_emb = np.asarray(
                    candidates[sel_idx].get("embedding", []),
                    dtype=np.float32,
                )
                if sel_emb.ndim > 0:
                    max_sim = max(max_sim, cosine(emb, sel_emb))

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return [{**candidates[i], "score": float(candidates[i].get("score", 0.0))} for i in selected]


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """Reciprocal Rank Fusion."""
    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content].copy()
        item["score"] = score
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

    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "mmr":
        from src._index_store import embed_query

        query_embedding = embed_query(query).tolist()
        for c in candidates:
            if "embedding" not in c:
                from src._index_store import embed_texts

                c["embedding"] = embed_texts([c["content"]])[0].tolist()
        return rerank_mmr(query_embedding, candidates, top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k)
    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    results = rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
