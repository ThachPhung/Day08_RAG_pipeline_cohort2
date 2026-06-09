"""
RAG Evaluation Pipeline — DeepEval-style metrics (heuristic offline) + A/B comparison.

Chạy từ repo root:
    python3 -m group_project.evaluation.eval_pipeline

Yêu cầu:
    - golden_dataset.json (≥15 Q&A)
    - Index đã build (group_project/index/ hoặc chạy lần đầu sẽ tự build)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"
RESULTS_PATH = EVAL_DIR / "results.md"

CONFIGS = {
    "hybrid_rerank": {
        "label": "Hybrid + Rerank (mặc định)",
        "retrieve_kwargs": {
            "use_semantic": True,
            "use_lexical": True,
            "use_reranking": True,
        },
    },
    "dense_only": {
        "label": "Dense-only (không BM25, không rerank)",
        "retrieve_kwargs": {
            "use_semantic": True,
            "use_lexical": False,
            "use_reranking": False,
        },
    },
}


def load_golden_dataset() -> list[dict]:
    with GOLDEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) > 1}


def _overlap_ratio(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def faithfulness(answer: str, contexts: list[str]) -> float:
    """Answer bám context: overlap câu trả lời với retrieval context."""
    if not answer.strip() or not contexts:
        return 0.0
    ctx_blob = " ".join(contexts)
    return _overlap_ratio(answer, ctx_blob)


def answer_relevancy(answer: str, question: str, expected_answer: str) -> float:
    """Câu trả lời liên quan câu hỏi và ground truth."""
    if not answer.strip():
        return 0.0
    q_score = _overlap_ratio(answer, question)
    gt_score = _overlap_ratio(answer, expected_answer)
    return 0.4 * q_score + 0.6 * gt_score


def context_recall(contexts: list[str], expected_context: str) -> float:
    """Retriever có lấy đủ evidence không (keyword từ expected_context)."""
    if not expected_context.strip():
        return 0.0
    keys = _tokens(expected_context)
    if not keys:
        return 0.0
    blob = " ".join(contexts).lower()
    hits = sum(1 for k in keys if k in blob)
    return hits / len(keys)


def context_precision(contexts: list[str], question: str) -> float:
    """Tỷ lệ chunks thực sự liên quan câu hỏi."""
    if not contexts:
        return 0.0
    q_tokens = _tokens(question)
    if not q_tokens:
        return 0.0
    relevant = 0
    for ctx in contexts:
        if _overlap_ratio(ctx, question) >= 0.05:
            relevant += 1
    return relevant / len(contexts)


def evaluate_config(
    golden_dataset: list[dict],
    config_name: str,
    retrieve_kwargs: dict,
    top_k: int = 5,
    sample_limit: int | None = None,
) -> dict:
    from group_project.pipeline import rag_query

    items = golden_dataset[:sample_limit] if sample_limit else golden_dataset
    rows = []
    metric_sums = {
        "faithfulness": 0.0,
        "answer_relevancy": 0.0,
        "context_recall": 0.0,
        "context_precision": 0.0,
    }

    for item in items:
        question = item["question"]
        result = rag_query(question, top_k=top_k, **retrieve_kwargs)
        contexts = [c.get("preview", c.get("content", "")) for c in result.get("sources", [])]
        if not contexts and result.get("context"):
            contexts = [result["context"]]

        scores = {
            "faithfulness": faithfulness(result["answer"], contexts),
            "answer_relevancy": answer_relevancy(
                result["answer"], question, item.get("expected_answer", "")
            ),
            "context_recall": context_recall(contexts, item.get("expected_context", "")),
            "context_precision": context_precision(contexts, question),
        }
        for k, v in scores.items():
            metric_sums[k] += v
        rows.append(
            {
                "question": question,
                "answer": result["answer"][:300],
                "scores": scores,
                "retrieval_source": result.get("retrieval_source", "none"),
            }
        )

    n = len(items) or 1
    averages = {k: round(v / n, 4) for k, v in metric_sums.items()}
    averages["average"] = round(sum(averages.values()) / 4, 4)
    return {"config": config_name, "averages": averages, "rows": rows}


def compare_configs(golden_dataset: list[dict], sample_limit: int | None = 20) -> dict:
    results = {}
    for name, cfg in CONFIGS.items():
        print(f"  Evaluating config: {name} ...")
        results[name] = evaluate_config(
            golden_dataset,
            name,
            cfg["retrieve_kwargs"],
            sample_limit=sample_limit,
        )
    return results


def _worst_performers(comparison: dict, top_n: int = 3) -> list[dict]:
    """Bottom questions theo faithfulness (config hybrid)."""
    hybrid = comparison.get("hybrid_rerank", {})
    rows = hybrid.get("rows", [])
    ranked = sorted(rows, key=lambda r: r["scores"]["faithfulness"])
    return ranked[:top_n]


def export_results(comparison: dict) -> str:
    hybrid = comparison["hybrid_rerank"]["averages"]
    dense = comparison["dense_only"]["averages"]

    def delta(a: float, b: float) -> str:
        d = a - b
        return f"{d:+.4f}"

    worst = _worst_performers(comparison)
    content = f"""# RAG Evaluation Results

## Framework sử dụng

**Heuristic offline metrics** (token overlap) — chạy được không cần API key.
Có thể nâng cấp sang DeepEval/RAGAS khi có `OPENAI_API_KEY`.

Chạy lại: `python3 -m group_project.evaluation.eval_pipeline`

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Δ |
|--------|---------------------------|----------------------|---|
| Faithfulness | {hybrid['faithfulness']:.4f} | {dense['faithfulness']:.4f} | {delta(hybrid['faithfulness'], dense['faithfulness'])} |
| Answer Relevance | {hybrid['answer_relevancy']:.4f} | {dense['answer_relevancy']:.4f} | {delta(hybrid['answer_relevancy'], dense['answer_relevancy'])} |
| Context Recall | {hybrid['context_recall']:.4f} | {dense['context_recall']:.4f} | {delta(hybrid['context_recall'], dense['context_recall'])} |
| Context Precision | {hybrid['context_precision']:.4f} | {dense['context_precision']:.4f} | {delta(hybrid['context_precision'], dense['context_precision'])} |
| **Average** | **{hybrid['average']:.4f}** | **{dense['average']:.4f}** | **{delta(hybrid['average'], dense['average'])}** |

---

## A/B Comparison Analysis

**Config A — hybrid_rerank:**
Semantic + BM25 → RRF merge → keyword rerank → PageIndex fallback khi score thấp.

**Config B — dense_only:**
Chỉ semantic search, không BM25, không rerank.

**Kết luận:**
Config A (hybrid + rerank) thường cho **context recall/precision** tốt hơn nhờ BM25 bắt đúng từ khóa pháp luật (Điều, Nghị định).
Dense-only yếu hơn với truy vấn có mã điều luật cụ thể nhưng nhẹ hơn khi index nhỏ.

---

## Worst Performers (Bottom 3 — Config A)

| # | Question | Faithfulness | Relevance | Recall | Failure Stage | Root Cause |
|---|----------|-------------|-----------|--------|---------------|------------|
"""
    for i, row in enumerate(worst, 1):
        s = row["scores"]
        q = row["question"][:70].replace("|", "/") + "..."
        content += (
            f"| {i} | {q} | {s['faithfulness']:.3f} | {s['answer_relevancy']:.3f} | "
            f"{s['context_recall']:.3f} | retrieval/generation | "
            f"Chunk không khớp expected_context hoặc câu trả lời từ chối xác minh |\n"
        )

    content += """
---

## Recommendations

### Cải tiến 1
**Action:** Tăng `top_k` retrieval lên 8–10 cho câu hỏi pháp luật dài.
**Expected impact:** Context recall tăng, đặc biệt với câu hỏi đa điều khoản.

### Cải tiến 2
**Action:** Ưu tiên chunk `type=legal` khi query chứa từ "luật", "điều", "nghị định".
**Expected impact:** Giảm nhiễu từ bài báo khi hỏi về văn bản pháp luật.

### Cải tiến 3
**Action:** Bổ sung Bộ luật Hình sự (Điều 249–256) vào dataset landing.
**Expected impact:** Trả lời chính xác hơn các câu hỏi hình phạt hình sự.
"""
    RESULTS_PATH.write_text(content, encoding="utf-8")
    return content


def main() -> None:
    print("=" * 60)
    print("RAG Evaluation Pipeline")
    print("=" * 60)

    dataset = load_golden_dataset()
    print(f"Loaded {len(dataset)} golden Q&A pairs")

    t0 = time.time()
    comparison = compare_configs(dataset, sample_limit=min(20, len(dataset)))
    export_results(comparison)
    elapsed = time.time() - t0

    print(f"\n✓ Results exported to {RESULTS_PATH}")
    print(f"  Time: {elapsed:.1f}s")
    for name, res in comparison.items():
        print(f"  {name}: avg={res['averages']['average']:.4f}")


if __name__ == "__main__":
    main()
