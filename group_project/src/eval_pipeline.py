"""
RAG Evaluation Pipeline.

This script evaluates the group RAG pipeline without requiring paid evaluator
APIs. It uses deterministic heuristic metrics so the evaluation can run locally
for demo:

    1. Load golden_dataset.json
    2. Run the RAG pipeline on every question
    3. Score faithfulness, answer relevance, context recall, context precision
    4. Compare two configs:
       - Config A: hybrid retrieval + reranking
       - Config B: hybrid retrieval without reranking
    5. Export a Markdown report to results.md

The metric names match DeepEval/RAGAS-style RAG evaluation, while the scoring
implementation is local and transparent for classroom demo.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import argparse
import shutil
from pathlib import Path
from typing import Callable


GROUP_PROJECT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(__file__).resolve().parents[2]

# Prefer the completed member pipeline in group_project/src. Keep project root
# second so shared files can still be found when needed.
for path in (str(GROUP_PROJECT_DIR), str(PROJECT_DIR)):
    if path in sys.path:
        sys.path.remove(path)
sys.path.insert(0, str(GROUP_PROJECT_DIR))
sys.path.insert(1, str(PROJECT_DIR))

from src.task10_generation import generate_with_citation
from src.task9_retrieval_pipeline import retrieve


EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"
RESULTS_PATH = EVAL_DIR / "results.md"
MIN_EXPECTED_CASES = 15
GROUP_STANDARDIZED_DIR = GROUP_PROJECT_DIR / "data" / "standardized"
ROOT_STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
GROUP_INDEX_DIR = GROUP_PROJECT_DIR / "data" / "index"
LOCAL_EMBEDDING_DIM = 384


MetricScores = dict[str, float]
CaseResult = dict[str, object]


def tokenize(text: str) -> list[str]:
    """Unicode-aware tokenizer for Vietnamese evaluation text."""
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def summarize_text(text: str, max_chars: int = 800) -> str:
    """Compact long text for terminal previews."""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def load_golden_dataset() -> list[dict]:
    """Load golden dataset from JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    required_keys = {"question", "expected_answer", "expected_context"}
    for idx, item in enumerate(dataset, 1):
        missing = required_keys - set(item)
        if missing:
            raise ValueError(f"Case #{idx} missing keys: {sorted(missing)}")
    return dataset


def ensure_group_standardized_data() -> None:
    """Ensure group_project/src pipeline has markdown data to index."""
    has_group_markdown = GROUP_STANDARDIZED_DIR.exists() and any(
        GROUP_STANDARDIZED_DIR.rglob("*.md")
    )
    if has_group_markdown:
        return

    if not ROOT_STANDARDIZED_DIR.exists() or not any(ROOT_STANDARDIZED_DIR.rglob("*.md")):
        raise FileNotFoundError(
            "No markdown data found. Expected files in group_project/data/standardized "
            "or data/standardized before running evaluation."
        )

    GROUP_STANDARDIZED_DIR.mkdir(parents=True, exist_ok=True)
    for item in ROOT_STANDARDIZED_DIR.iterdir():
        destination = GROUP_STANDARDIZED_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, destination)


def install_offline_embedding_fallback() -> None:
    """
    Patch the group pipeline to avoid downloading sentence-transformers models.

    The completed group src uses SentenceTransformer by default. For evaluation
    without network/API keys, this deterministic hash embedding keeps semantic
    search runnable and preserves the same retrieve/generate interfaces.
    """
    import hashlib

    import numpy as np
    import src._index_store as index_store
    import src.task5_semantic_search as task5

    def _embed_texts(texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), LOCAL_EMBEDDING_DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % LOCAL_EMBEDDING_DIM
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                matrix[row, idx] += sign
            norm = np.linalg.norm(matrix[row])
            if norm:
                matrix[row] /= norm
        return matrix

    def _embed_query(query: str) -> np.ndarray:
        return _embed_texts([query])[0]

    index_store._embedding_model = "offline-hash-embedding"
    index_store.embed_texts = _embed_texts
    index_store.embed_query = _embed_query
    task5.embed_query = _embed_query

    # If task4 was already imported, patch its copied function reference too.
    task4 = sys.modules.get("src.task4_chunking_indexing")
    if task4 is not None:
        task4.embed_texts = _embed_texts

    # Rebuild index with the deterministic local embedding to avoid stale/empty
    # artifacts from previous failed online model attempts.
    if GROUP_INDEX_DIR.exists():
        shutil.rmtree(GROUP_INDEX_DIR)


def _token_set(text: str) -> set[str]:
    stopwords = {
        "và",
        "là",
        "của",
        "có",
        "cho",
        "theo",
        "về",
        "trong",
        "những",
        "các",
        "một",
        "được",
        "không",
        "nào",
        "gì",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
    }
    return {token for token in tokenize(text) if len(token) > 1 and token not in stopwords}


def _coverage(reference: str, candidate: str) -> float:
    """Return how much of reference token set appears in candidate."""
    ref_tokens = _token_set(reference)
    if not ref_tokens:
        return 0.0
    candidate_tokens = _token_set(candidate)
    return len(ref_tokens & candidate_tokens) / len(ref_tokens)


def _citation_score(answer: str) -> float:
    """Simple citation presence score."""
    citations = re.findall(r"\[[^\]]+\]", answer)
    return 1.0 if citations else 0.0


def _format_sources(sources: list[dict]) -> str:
    return "\n".join(source.get("content", "") for source in sources)


def calculate_metrics(item: dict, answer: str, sources: list[dict]) -> MetricScores:
    """
    Calculate local RAG metrics on a 0..1 scale.

    - Faithfulness: answer terms should be supported by retrieved context and
      answer should include citations.
    - Answer relevance: answer should cover the question and expected answer.
    - Context recall: retrieved context should include expected context/answer.
    - Context precision: retrieved context should focus on query terms.
    """
    question = item["question"]
    expected_answer = item["expected_answer"]
    expected_context = item["expected_context"]
    retrieved_context = _format_sources(sources)

    answer_supported = _coverage(answer, retrieved_context)
    faithfulness = min(1.0, 0.8 * answer_supported + 0.2 * _citation_score(answer))

    relevance_to_question = _coverage(question, answer)
    relevance_to_expected = _coverage(expected_answer, answer)
    answer_relevance = min(1.0, 0.45 * relevance_to_question + 0.55 * relevance_to_expected)

    recall_expected_answer = _coverage(expected_answer, retrieved_context)
    recall_expected_context = _coverage(expected_context, retrieved_context)
    context_recall = min(1.0, 0.7 * recall_expected_answer + 0.3 * recall_expected_context)

    useful_context_chunks = 0
    for source in sources:
        content = source.get("content", "")
        chunk_score = max(_coverage(question, content), _coverage(expected_answer, content))
        if chunk_score >= 0.2:
            useful_context_chunks += 1
    context_precision = useful_context_chunks / len(sources) if sources else 0.0

    return {
        "faithfulness": round(faithfulness, 3),
        "answer_relevance": round(answer_relevance, 3),
        "context_recall": round(context_recall, 3),
        "context_precision": round(context_precision, 3),
    }


def _average_metrics(case_results: list[CaseResult]) -> MetricScores:
    metrics = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]
    if not case_results:
        return {metric: 0.0 for metric in metrics}

    return {
        metric: round(
            statistics.mean(float(case["metrics"][metric]) for case in case_results),
            3,
        )
        for metric in metrics
    }


def _overall_score(metrics: MetricScores) -> float:
    return round(statistics.mean(metrics.values()), 3) if metrics else 0.0


def run_config(
    golden_dataset: list[dict],
    config_name: str,
    generate_fn: Callable[[str], dict],
) -> dict:
    """Run one RAG config across the golden dataset."""
    cases: list[CaseResult] = []
    for item in golden_dataset:
        result = generate_fn(item["question"])
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        metrics = calculate_metrics(item, answer, sources)
        cases.append(
            {
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "expected_context": item["expected_context"],
                "answer": answer,
                "sources": sources,
                "retrieval_source": result.get("retrieval_source", "unknown"),
                "metrics": metrics,
                "average": _overall_score(metrics),
            }
        )

    averages = _average_metrics(cases)
    return {
        "config_name": config_name,
        "averages": averages,
        "overall": _overall_score(averages),
        "cases": cases,
    }


def generate_with_no_rerank(query: str, top_k: int = 5) -> dict:
    """Generation wrapper for Config B: hybrid retrieval without reranking."""
    chunks = retrieve(query, top_k=top_k, use_reranking=False)
    if not chunks:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": [],
            "retrieval_source": "none",
        }

    answer_parts = []
    for chunk in chunks[:3]:
        source = chunk.get("metadata", {}).get("source", "Nguồn không rõ").replace(".md", "")
        snippet = summarize_text(chunk.get("content", ""), max_chars=320)
        answer_parts.append(f"{snippet} [{source}]")

    return {
        "answer": "Dựa trên các nguồn đã truy xuất, thông tin liên quan là: "
        + " ".join(answer_parts),
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none",
    }


def evaluate_with_local_heuristics(golden_dataset: list[dict]) -> dict:
    """Evaluate Config A with the default generation pipeline."""
    return run_config(
        golden_dataset=golden_dataset,
        config_name="Config A: hybrid + rerank",
        generate_fn=lambda query: generate_with_citation(query, top_k=5),
    )


def compare_configs(golden_dataset: list[dict]) -> dict:
    """Run A/B comparison between reranking and no-reranking configs."""
    config_a = evaluate_with_local_heuristics(golden_dataset)
    config_b = run_config(
        golden_dataset=golden_dataset,
        config_name="Config B: hybrid no rerank",
        generate_fn=lambda query: generate_with_no_rerank(query, top_k=5),
    )
    return {"config_a": config_a, "config_b": config_b}


def _metric_label(metric: str) -> str:
    return {
        "faithfulness": "Faithfulness",
        "answer_relevance": "Answer Relevance",
        "context_recall": "Context Recall",
        "context_precision": "Context Precision",
    }[metric]


def _delta(a: float, b: float) -> str:
    value = round(a - b, 3)
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.3f}"


def _worst_cases(config_result: dict, limit: int = 3) -> list[CaseResult]:
    return sorted(config_result["cases"], key=lambda case: case["average"])[:limit]


def export_results(comparison: dict, dataset_size: int) -> Path:
    """Export evaluation results to results.md."""
    config_a = comparison["config_a"]
    config_b = comparison["config_b"]
    metrics = ["faithfulness", "answer_relevance", "context_recall", "context_precision"]

    lines = [
        "# RAG Evaluation Results",
        "",
        "## Framework sử dụng",
        "",
        "Framework: **Local heuristic evaluator**.",
        "",
        "Lý do chọn: chạy được offline, không cần OpenAI/DeepEval/RAGAS API key, "
        "phù hợp để demo nhanh pipeline nhóm. Các metric vẫn bám theo 4 nhóm "
        "đánh giá RAG phổ biến: faithfulness, answer relevance, context recall, "
        "context precision.",
        "",
        f"Số test cases hiện có: **{dataset_size}**.",
    ]

    if dataset_size < MIN_EXPECTED_CASES:
        lines.extend(
            [
                "",
                f"> Warning: yêu cầu bài nhóm là tối thiểu {MIN_EXPECTED_CASES} Q&A pairs. "
                f"Dataset hiện tại mới có {dataset_size}; cần bổ sung thêm trước khi nộp chính thức.",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Overall Scores",
            "",
            "| Metric | Config A (hybrid + rerank) | Config B (hybrid no rerank) | Delta |",
            "|--------|-----------------------------|------------------------------|-------|",
        ]
    )

    for metric in metrics:
        score_a = config_a["averages"][metric]
        score_b = config_b["averages"][metric]
        lines.append(
            f"| {_metric_label(metric)} | {score_a:.3f} | {score_b:.3f} | {_delta(score_a, score_b)} |"
        )

    lines.append(
        f"| **Average** | **{config_a['overall']:.3f}** | **{config_b['overall']:.3f}** | "
        f"**{_delta(config_a['overall'], config_b['overall'])}** |"
    )

    winner = "Config A" if config_a["overall"] >= config_b["overall"] else "Config B"
    lines.extend(
        [
            "",
            "---",
            "",
            "## A/B Comparison Analysis",
            "",
            "**Config A:** Hybrid retrieval gồm semantic search + lexical BM25, merge bằng RRF, "
            "sau đó rerank local theo độ liên quan với query.",
            "",
            "**Config B:** Hybrid retrieval giống Config A nhưng bỏ bước reranking để kiểm tra "
            "ảnh hưởng của reranker.",
            "",
            f"**Kết luận:** {winner} có điểm trung bình cao hơn trong lần chạy hiện tại. "
            "Nếu Config A tốt hơn, reranking giúp đẩy chunk liên quan lên đầu. Nếu Config B "
            "tương đương hoặc tốt hơn, dataset/context hiện tại còn nhỏ nên lợi ích reranking "
            "chưa thể hiện rõ.",
            "",
            "---",
            "",
            "## Worst Performers (Bottom 3 - Config A)",
            "",
            "| # | Question | Faithfulness | Relevance | Recall | Precision | Root Cause |",
            "|---|----------|--------------|-----------|--------|-----------|------------|",
        ]
    )

    for idx, case in enumerate(_worst_cases(config_a), 1):
        case_metrics = case["metrics"]
        question = str(case["question"]).replace("|", "\\|")
        root_cause = (
            "Retriever chưa lấy đủ expected context hoặc dữ liệu chuẩn hóa còn thiếu chi tiết."
            if case_metrics["context_recall"] < 0.5
            else "Answer extractive còn ngắn, chưa bao phủ đủ expected answer."
        )
        lines.append(
            f"| {idx} | {question} | {case_metrics['faithfulness']:.3f} | "
            f"{case_metrics['answer_relevance']:.3f} | {case_metrics['context_recall']:.3f} | "
            f"{case_metrics['context_precision']:.3f} | {root_cause} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Recommendations",
            "",
            "### Cải tiến 1",
            "**Action:** Bổ sung golden dataset lên tối thiểu 15 Q&A và phủ đều nhóm câu hỏi pháp luật, cai nghiện, danh mục chất ma tuý, tin tức nghệ sĩ.",
            "",
            "**Expected impact:** Kết quả đánh giá ổn định hơn và đáp ứng đúng rubric bài nhóm.",
            "",
            "### Cải tiến 2",
            "**Action:** Convert PDF pháp luật bằng parser mạnh hơn để lấy được điều/khoản chi tiết thay vì chỉ dùng fallback summary.",
            "",
            "**Expected impact:** Tăng context recall cho câu hỏi cần căn cứ điều luật cụ thể.",
            "",
            "### Cải tiến 3",
            "**Action:** Thay local heuristic reranker bằng cross-encoder multilingual hoặc Jina Reranker khi có API key.",
            "",
            "**Expected impact:** Tăng answer relevance và context precision trên các câu hỏi dài hoặc nhiều thực thể.",
            "",
        ]
    )

    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    return RESULTS_PATH


def print_case_results(comparison: dict) -> None:
    """Print per-question scores to terminal for demo/debug."""
    config_a_cases = comparison["config_a"]["cases"]
    config_b_cases = comparison["config_b"]["cases"]

    print("\nPer-case evaluation results")
    print("=" * 80)
    for idx, (case_a, case_b) in enumerate(zip(config_a_cases, config_b_cases), 1):
        metrics_a = case_a["metrics"]
        metrics_b = case_b["metrics"]
        top_source = "N/A"
        sources = case_a.get("sources", [])
        if sources:
            top_source = sources[0].get("metadata", {}).get("source", "N/A")

        print(f"\n[{idx}] {case_a['question']}")
        print(f"Expected context: {case_a['expected_context']}")
        print(f"Top source: {top_source}")
        print(
            "Config A metrics: "
            f"faithfulness={metrics_a['faithfulness']:.3f}, "
            f"relevance={metrics_a['answer_relevance']:.3f}, "
            f"recall={metrics_a['context_recall']:.3f}, "
            f"precision={metrics_a['context_precision']:.3f}, "
            f"avg={case_a['average']:.3f}"
        )
        print(
            "Config B metrics: "
            f"faithfulness={metrics_b['faithfulness']:.3f}, "
            f"relevance={metrics_b['answer_relevance']:.3f}, "
            f"recall={metrics_b['context_recall']:.3f}, "
            f"precision={metrics_b['context_precision']:.3f}, "
            f"avg={case_b['average']:.3f}"
        )
        print(f"Answer preview: {summarize_text(str(case_a['answer']), max_chars=260)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG evaluation pipeline.")
    parser.add_argument(
        "--print-cases",
        action="store_true",
        help="Print every per-question evaluation result to terminal.",
    )
    args = parser.parse_args()

    ensure_group_standardized_data()
    install_offline_embedding_fallback()
    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} test cases")
    if len(golden_dataset) < MIN_EXPECTED_CASES:
        print(
            f"Warning: golden_dataset.json should contain at least "
            f"{MIN_EXPECTED_CASES} cases before final submission."
        )

    comparison = compare_configs(golden_dataset)
    results_path = export_results(comparison, dataset_size=len(golden_dataset))
    print(f"Saved evaluation report to {results_path}")
    print(f"Config A overall: {comparison['config_a']['overall']:.3f}")
    print(f"Config B overall: {comparison['config_b']['overall']:.3f}")

    if args.print_cases:
        print_case_results(comparison)


if __name__ == "__main__":
    main()
