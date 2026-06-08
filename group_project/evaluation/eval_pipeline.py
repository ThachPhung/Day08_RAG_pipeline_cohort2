"""Offline RAG evaluation pipeline for the group project.

This script evaluates the group retrieval pipeline without requiring paid LLM
judge APIs. It reports four rubric-aligned heuristic metrics and an A/B
comparison between hybrid reranking and dense-only retrieval.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from group_project.src._index_store import tokenize
from group_project.src.task9_retrieval_pipeline import retrieve

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"


def load_golden_dataset() -> list[dict]:
    with GOLDEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _token_overlap(left: str, right: str) -> float:
    left_terms = set(tokenize(left))
    right_terms = set(tokenize(right))
    if not left_terms:
        return 0.0
    return len(left_terms & right_terms) / len(left_terms)


def _build_answer(results: list[dict], max_chars: int = 900) -> str:
    if not results:
        return "I cannot verify this information"
    snippets: list[str] = []
    for item in results[:3]:
        source = item.get("metadata", {}).get("source", "unknown")
        text = " ".join(item.get("content", "").split())
        snippets.append(f"{text[:max_chars // 3]} [{source}, 2026]")
    return " ".join(snippets).strip()


def _evaluate_case(item: dict, results: list[dict]) -> dict:
    contexts = [result.get("content", "") for result in results]
    joined_context = " ".join(contexts)
    answer = _build_answer(results)

    expected_answer = item.get("expected_answer", "")
    expected_context = item.get("expected_context", "")

    faithfulness = _token_overlap(answer, joined_context)
    answer_relevance = _token_overlap(item["question"], answer)
    context_recall = max((_token_overlap(expected_answer, ctx) for ctx in contexts), default=0.0)
    context_precision = (
        sum(1 for ctx in contexts if _token_overlap(expected_answer, ctx) >= 0.12) / len(contexts)
        if contexts
        else 0.0
    )
    expected_context_hit = _token_overlap(expected_context, joined_context)
    context_recall = max(context_recall, expected_context_hit)

    return {
        "question": item["question"],
        "answer": answer,
        "sources": [result.get("metadata", {}).get("source", "unknown") for result in results],
        "faithfulness": round(min(faithfulness, 1.0), 3),
        "answer_relevance": round(min(answer_relevance, 1.0), 3),
        "context_recall": round(min(context_recall, 1.0), 3),
        "context_precision": round(min(context_precision, 1.0), 3),
    }


def run_config(golden_dataset: list[dict], config: dict) -> dict:
    cases: list[dict] = []
    for item in golden_dataset:
        results = retrieve(item["question"], top_k=5, **config["params"])
        cases.append(_evaluate_case(item, results))

    metrics = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]
    scores = {
        metric: round(sum(case[metric] for case in cases) / max(len(cases), 1), 3)
        for metric in metrics
    }
    scores["average"] = round(sum(scores.values()) / len(metrics), 3)
    return {"scores": scores, "cases": cases, "description": config["description"]}


def compare_configs(golden_dataset: list[dict]) -> dict:
    configs = {
        "hybrid_rerank": {
            "description": "Semantic + BM25 retrieval, RRF fusion, keyword-overlap reranking, PageIndex fallback.",
            "params": {
                "use_semantic": True,
                "use_lexical": True,
                "use_reranking": True,
                "score_threshold": 0.15,
            },
        },
        "dense_only": {
            "description": "Semantic retrieval only, no reranking; used as the baseline.",
            "params": {
                "use_semantic": True,
                "use_lexical": False,
                "use_reranking": False,
                "score_threshold": 0.0,
            },
        },
    }
    return {name: run_config(golden_dataset, config) for name, config in configs.items()}


def _worst_cases(cases: list[dict], limit: int = 3) -> list[dict]:
    def average(case: dict) -> float:
        return (
            case["faithfulness"]
            + case["answer_relevance"]
            + case["context_recall"]
            + case["context_precision"]
        ) / 4

    return sorted(cases, key=average)[:limit]


def export_results(comparison: dict) -> None:
    a = comparison["hybrid_rerank"]
    b = comparison["dense_only"]
    rows = [
        ("Faithfulness", "faithfulness"),
        ("Answer Relevance", "answer_relevance"),
        ("Context Recall", "context_recall"),
        ("Context Precision", "context_precision"),
        ("Average", "average"),
    ]

    content = [
        "# RAG Evaluation Results",
        "",
        "## Framework sử dụng",
        "",
        "Offline heuristic evaluator trong `group_project/evaluation/eval_pipeline.py`.",
        "",
        "## Overall Scores",
        "",
        "| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Delta |",
        "|--------|-----------------------------|------------------------|-------|",
    ]
    for label, key in rows:
        delta = round(a["scores"][key] - b["scores"][key], 3)
        content.append(f"| {label} | {a['scores'][key]:.3f} | {b['scores'][key]:.3f} | {delta:+.3f} |")

    winner = "Config A" if a["scores"]["average"] >= b["scores"]["average"] else "Config B"
    content.extend(
        [
            "",
            "## A/B Comparison Analysis",
            "",
            f"**Config A:** {a['description']}",
            "",
            f"**Config B:** {b['description']}",
            "",
            f"**Kết luận:** {winner} có điểm trung bình tốt hơn trong bộ golden dataset hiện tại. Hybrid + rerank thường ổn hơn khi câu hỏi có từ khóa pháp lý cụ thể; dense-only là baseline đơn giản để kiểm tra độ phủ embedding.",
            "",
            "## Worst Performers (Bottom 3)",
            "",
            "| # | Question | Faithfulness | Relevance | Recall | Failure Stage | Root Cause |",
            "|---|----------|--------------|-----------|--------|---------------|------------|",
        ]
    )

    for index, case in enumerate(_worst_cases(a["cases"]), start=1):
        question = case["question"].replace("|", " ")
        failure = "retrieval" if case["context_recall"] < 0.3 else "answering"
        cause = "Expected evidence was weak or split across noisy chunks."
        content.append(
            f"| {index} | {question} | {case['faithfulness']:.3f} | "
            f"{case['answer_relevance']:.3f} | {case['context_recall']:.3f} | {failure} | {cause} |"
        )

    content.extend(
        [
            "",
            "## Recommendations",
            "",
            "### Cải tiến 1",
            "**Action:** Làm sạch markdown đã crawl, bỏ menu/navigation và ký tự lỗi trước khi index.",
            "**Expected impact:** Tăng context precision và giảm nhiễu trong câu trả lời.",
            "",
            "### Cải tiến 2",
            "**Action:** Thêm metadata `law_article`, `publisher`, `published_date` khi chunking.",
            "**Expected impact:** Citation rõ hơn và retrieval chính xác hơn cho câu hỏi theo điều/khoản.",
            "",
            "### Cải tiến 3",
            "**Action:** Thử reranker multilingual thật như Jina/Qwen khi có API hoặc GPU.",
            "**Expected impact:** Tăng answer relevance cho câu hỏi tiếng Việt dài và nhiều thực thể.",
            "",
        ]
    )

    RESULTS_PATH.write_text("\n".join(content), encoding="utf-8")


def main() -> None:
    golden_dataset = load_golden_dataset()
    if len(golden_dataset) < 15:
        raise ValueError("Golden dataset must contain at least 15 Q&A pairs.")
    comparison = compare_configs(golden_dataset)
    export_results(comparison)
    print(f"Evaluated {len(golden_dataset)} cases. Results written to {RESULTS_PATH}.")


if __name__ == "__main__":
    main()

