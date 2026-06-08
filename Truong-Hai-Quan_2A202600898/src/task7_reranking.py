"""
Task 7 — Reranking Module.

Cung cấp 3 phương pháp + 1 interface thống nhất:
    - cross_encoder: chấm lại độ liên quan query↔doc.
        Ưu tiên Jina Reranker API (nếu có JINA_API_KEY) → multilingual, đúng
        "cross-encoder" thật. Không có key thì fallback chấm bằng cosine của
        OpenAI embeddings; không có cả mạng thì fallback overlap từ khoá.
    - mmr: Maximal Marginal Relevance — cân bằng relevance & diversity.
    - rrf: Reciprocal Rank Fusion — gộp nhiều ranked list (dùng ở Task 9).

Interface chính: rerank(query, candidates, top_k, method="cross_encoder").
"""

import math
import os

import numpy as np

# Import rag_common ở top-level để kích hoạt load_dotenv() (đọc JINA_API_KEY từ .env)
# và ép UTF-8 stdout — nếu không, chạy task7 độc lập sẽ không thấy key → rớt fallback.
from src.rag_common import _force_utf8_stdout

_force_utf8_stdout()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _overlap_score(query: str, text: str) -> float:
    """Fallback offline: tỉ lệ token query xuất hiện trong text."""
    from src.rag_common import tokenize_vi

    q = set(tokenize_vi(query))
    if not q:
        return 0.0
    d = set(tokenize_vi(text))
    return len(q & d) / len(q)


# ---------------------------------------------------------------------------
# Cross-encoder
# ---------------------------------------------------------------------------
def _rerank_jina(query: str, candidates: list[dict], top_k: int):
    """Jina Reranker v2 multilingual qua API. Trả None nếu không khả dụng."""
    api_key = os.environ.get("JINA_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import requests

        resp = requests.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": [c["content"] for c in candidates],
                "top_n": top_k,
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = []
        for r in resp.json()["results"]:
            item = dict(candidates[r["index"]])
            item["score"] = float(r["relevance_score"])
            out.append(item)
        return out
    except Exception:
        return None


def _rerank_embedding(query: str, candidates: list[dict], top_k: int):
    """Chấm lại bằng cosine của OpenAI embeddings. None nếu lỗi (vd: không mạng)."""
    try:
        from src.rag_common import embed_texts

        vecs = embed_texts([query] + [c["content"] for c in candidates])
        qv, dvs = vecs[0], vecs[1:]
        out = []
        for c, dv in zip(candidates, dvs):
            item = dict(c)
            item["score"] = _cosine(qv, dv)
            out.append(item)
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:top_k]
    except Exception:
        return None


def rerank_cross_encoder(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Cross-encoder rerank với fallback nhiều tầng (luôn trả về kết quả)."""
    if not candidates:
        return []

    for fn in (_rerank_jina, _rerank_embedding):
        res = fn(query, candidates, top_k)
        if res is not None:
            return res

    # Fallback cuối: overlap từ khoá (offline, không phụ thuộc gì)
    out = []
    for c in candidates:
        item = dict(c)
        item["score"] = _overlap_score(query, c["content"])
        out.append(item)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_k]


# ---------------------------------------------------------------------------
# MMR
# ---------------------------------------------------------------------------
def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance: chọn doc vừa relevant vừa khác các doc đã chọn.
    MMR = λ·sim(query, doc) - (1-λ)·max sim(doc, đã_chọn)
    Yêu cầu mỗi candidate có 'embedding'.
    """
    if not candidates:
        return []
    selected: list[int] = []
    remaining = list(range(len(candidates)))

    while remaining and len(selected) < top_k:
        best_idx, best = None, -math.inf
        for idx in remaining:
            emb = candidates[idx].get("embedding")
            relevance = _cosine(query_embedding, emb) if emb is not None else 0.0
            max_sim = 0.0
            for s in selected:
                semb = candidates[s].get("embedding")
                if emb is not None and semb is not None:
                    max_sim = max(max_sim, _cosine(emb, semb))
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr > best:
                best, best_idx = mmr, idx
        selected.append(best_idx)
        remaining.remove(best_idx)

    out = []
    for rank, i in enumerate(selected):
        item = dict(candidates[i])
        item["score"] = float(len(selected) - rank)  # điểm theo thứ hạng MMR
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# RRF
# ---------------------------------------------------------------------------
def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion: RRF(d) = Σ 1/(k + rank_r(d)).
    Gộp nhiều ranked list (vd dense + lexical) không cần chuẩn hoá score.
    """
    rrf_scores: dict[str, float] = {}
    content_map: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            content_map[key] = item

    ordered = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for content, score in ordered[:top_k]:
        item = dict(content_map[content])
        item["score"] = float(score)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------
def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "cross_encoder",
) -> list[dict]:
    """Interface thống nhất. Mặc định cross_encoder (có fallback an toàn)."""
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "mmr":
        from src.rag_common import embed_query

        qv = embed_query(query)
        # đảm bảo candidates có embedding
        from src.rag_common import embed_texts

        missing = [c for c in candidates if "embedding" not in c]
        if missing:
            embs = embed_texts([c["content"] for c in missing])
            for c, e in zip(missing, embs):
                c["embedding"] = e
        return rerank_mmr(qv, candidates, top_k)
    if method == "rrf":
        return rerank_rrf([candidates], top_k)
    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    dummy = [
        {"content": "Điều 248: Tội tàng trữ trái phép chất ma tuý", "score": 0.8, "metadata": {}},
        {"content": "Nghệ sĩ X bị bắt vì sử dụng ma tuý", "score": 0.7, "metadata": {}},
        {"content": "Hình phạt tù từ 2-7 năm cho tội tàng trữ", "score": 0.6, "metadata": {}},
    ]
    for r in rerank("hình phạt tàng trữ ma tuý", dummy, top_k=2):
        print(f"[{r['score']:.3f}] {r['content']}")
