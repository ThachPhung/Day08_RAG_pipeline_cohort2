"""
<<<<<<< HEAD
Task 7 — Reranking Module.

Chọn 1 trong các phương pháp:
    - Cross-encoder reranker: Jina Reranker v2 (multilingual) hoặc Qwen3-Reranker
    - MMR (Maximal Marginal Relevance): tự implement
    - RRF (Reciprocal Rank Fusion): tự implement

Nếu dùng MMR hoặc RRF, đảm bảo hiểu và giải thích được cơ chế.
"""

from typing import Optional


=======
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


>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
<<<<<<< HEAD
    Rerank candidates sử dụng cross-encoder model.

    Args:
        query: Câu truy vấn
        candidates: List of {'content': str, 'score': float, 'metadata': dict}
        top_k: Số lượng kết quả sau rerank

    Returns:
        List of top_k candidates, re-scored và sorted by rerank_score descending.
    """
    # TODO: Implement cross-encoder reranking
    #
    # Option A: Jina Reranker API
    # import requests
    # response = requests.post(
    #     "https://api.jina.ai/v1/rerank",
    #     headers={"Authorization": f"Bearer {JINA_API_KEY}"},
    #     json={
    #         "model": "jina-reranker-v2-base-multilingual",
    #         "query": query,
    #         "documents": [c["content"] for c in candidates],
    #         "top_n": top_k
    #     }
    # )
    # reranked = response.json()["results"]
    # return [
    #     {**candidates[r["index"]], "score": r["relevance_score"]}
    #     for r in reranked
    # ]
    #
    # Option B: Local model (Qwen3-Reranker)
    # from transformers import AutoModelForSequenceClassification, AutoTokenizer
    # ...
    raise NotImplementedError("Implement rerank_cross_encoder")
=======
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
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
<<<<<<< HEAD
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))

    Args:
        query_embedding: Vector embedding của query
        candidates: List of {'content': str, 'score': float, 'embedding': list, 'metadata': dict}
        top_k: Số lượng kết quả
        lambda_param: Trade-off giữa relevance (1.0) và diversity (0.0)

    Returns:
        List of top_k candidates selected by MMR.
    """
    # TODO: Implement MMR
    #
    # selected = []
    # remaining = list(range(len(candidates)))
    #
    # for _ in range(min(top_k, len(candidates))):
    #     best_idx = None
    #     best_score = float('-inf')
    #
    #     for idx in remaining:
    #         # Relevance to query
    #         relevance = cosine_sim(query_embedding, candidates[idx]["embedding"])
    #
    #         # Max similarity to already selected
    #         max_sim_to_selected = 0
    #         for sel_idx in selected:
    #             sim = cosine_sim(candidates[idx]["embedding"], candidates[sel_idx]["embedding"])
    #             max_sim_to_selected = max(max_sim_to_selected, sim)
    #
    #         # MMR score
    #         mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
    #
    #         if mmr_score > best_score:
    #             best_score = mmr_score
    #             best_idx = idx
    #
    #     selected.append(best_idx)
    #     remaining.remove(best_idx)
    #
    # return [candidates[i] for i in selected]
    raise NotImplementedError("Implement rerank_mmr")
=======
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
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
<<<<<<< HEAD
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Args:
        ranked_lists: List of ranked result lists (mỗi list từ 1 ranker)
        top_k: Số lượng kết quả cuối cùng
        k: Smoothing constant (default=60, từ paper Cormack et al. 2009)

    Returns:
        List of top_k candidates sorted by RRF score descending.
    """
    # TODO: Implement RRF
    #
    # rrf_scores = {}  # content -> score
    # content_map = {}  # content -> full dict
    #
    # for ranked_list in ranked_lists:
    #     for rank, item in enumerate(ranked_list, 1):
    #         key = item["content"]
    #         rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
    #         content_map[key] = item
    #
    # # Sort by RRF score
    # sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    #
    # results = []
    # for content, score in sorted_items[:top_k]:
    #     item = content_map[content].copy()
    #     item["score"] = score
    #     results.append(item)
    #
    # return results
    raise NotImplementedError("Implement rerank_rrf")


# =============================================================================
# Main rerank interface
# =============================================================================

=======
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


>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
<<<<<<< HEAD
    method: str = "cross_encoder",  # "cross_encoder" | "mmr" | "rrf"
) -> list[dict]:
    """
    Unified reranking interface.

    Args:
        query: Câu truy vấn
        candidates: Danh sách candidates từ retrieval
        top_k: Số lượng kết quả sau rerank
        method: Phương pháp reranking

    Returns:
        List of top_k reranked candidates.
    """
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        # Cần query_embedding - embed query trước
        raise NotImplementedError("Call rerank_mmr with query_embedding")
    elif method == "rrf":
        # RRF cần nhiều ranked lists - gọi riêng
        raise NotImplementedError("Call rerank_rrf with ranked_lists")
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    # Test with dummy data
=======
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
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
    dummy_candidates = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    results = rerank("hình phạt tàng trữ ma tuý", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
