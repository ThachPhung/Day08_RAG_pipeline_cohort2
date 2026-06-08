"""Citation-aware answering for the group RAG chatbot.

This file belongs to the group project. It intentionally does not modify or
depend on the individual Task 10 generation logic. The only individual module it
uses is Task 9 retrieval, because the group answer component needs retrieved
context before it can cite sources.

Responsibilities:
    - format sources clearly for UI display;
    - build answers only from retrieved evidence;
    - add citations in [source | type | chunk] format;
    - refuse to verify when evidence is weak, reducing hallucination risk.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.task9_retrieval_pipeline import retrieve

TOP_K = 5
MIN_EVIDENCE_SCORE = 0.05

ANTI_HALLUCINATION_POLICY = """Use only retrieved context.
Do not invent penalties, dates, names, laws, or article numbers.
Every factual bullet must include a source citation.
If retrieved evidence is weak or absent, state that the information cannot be
verified from available sources."""


def source_label(chunk: dict, fallback_index: int) -> str:
    """Return a stable source label for citations."""
    metadata = chunk.get("metadata", {})
    source = metadata.get("source") or metadata.get("path") or f"source_{fallback_index}"
    doc_type = metadata.get("type", "unknown")
    chunk_index = metadata.get("chunk_index", "?")
    return f"{source} | {doc_type} | chunk {chunk_index}"


def format_sources(chunks: list[dict]) -> list[dict]:
    """Format sources for Streamlit/Chainlit display."""
    formatted = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        formatted.append(
            {
                "label": source_label(chunk, index),
                "source": metadata.get("source", "unknown"),
                "type": metadata.get("type", "unknown"),
                "chunk_index": metadata.get("chunk_index", "?"),
                "score": round(float(chunk.get("score", 0.0)), 4),
                "preview": " ".join(chunk.get("content", "").split())[:260],
            }
        )
    return formatted


def format_context(chunks: list[dict]) -> str:
    """Build a readable context block with source labels."""
    parts = []
    for index, chunk in enumerate(chunks, 1):
        label = source_label(chunk, index)
        score = float(chunk.get("score", 0.0))
        content = chunk.get("content", "").strip()
        parts.append(f"[Source {index}: {label} | score={score:.3f}]\n{content}")
    return "\n\n---\n\n".join(parts)


def _query_terms(question: str) -> set[str]:
    return set(re.findall(r"\w+", question.lower(), flags=re.UNICODE))


def _sentence_candidates(content: str) -> list[str]:
    cleaned = " ".join(content.split())
    sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    blocked = {
        "source:",
        "crawled:",
        "document type:",
        "bạn cần biết",
        "tiện ích",
        "đăng nhập",
        "bình luận",
        "quảng cáo",
    }
    candidates = []
    for sentence in sentences:
        sentence = sentence.strip(" -•\t")
        lowered = sentence.lower()
        if len(sentence) < 45:
            continue
        if sentence.startswith("#") or any(marker in lowered for marker in blocked):
            continue
        candidates.append(sentence)
    return candidates


def select_evidence(question: str, chunks: list[dict], max_items: int = 3) -> list[dict]:
    """Select evidence sentences from retrieved chunks."""
    query_terms = _query_terms(question)
    legal_intent_terms = {"luật", "nghị", "định", "hình", "phạt", "quy", "điều", "tội"}
    prefer_legal = bool(query_terms & legal_intent_terms)
    scored_evidence = []

    for index, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        label = source_label(chunk, index)
        for sentence in _sentence_candidates(chunk.get("content", ""))[:4]:
            sentence_terms = set(re.findall(r"\w+", sentence.lower(), flags=re.UNICODE))
            overlap = len(query_terms & sentence_terms)
            evidence_score = float(chunk.get("score", 0.0)) + overlap * 0.03
            if prefer_legal and metadata.get("type") == "legal":
                evidence_score += 0.25
            scored_evidence.append(
                {
                    "score": evidence_score,
                    "sentence": sentence,
                    "label": label,
                }
            )

    scored_evidence.sort(key=lambda item: item["score"], reverse=True)
    return scored_evidence[:max_items]


def has_enough_evidence(chunks: list[dict]) -> bool:
    """Check whether retrieval is strong enough to answer."""
    if not chunks:
        return False
    best_score = max(float(chunk.get("score", 0.0)) for chunk in chunks)
    return best_score >= MIN_EVIDENCE_SCORE


def answer_question(question: str, top_k: int = TOP_K) -> dict:
    """
    Answer a user question with grounded citations.

    Returns:
        {
            "answer": str,
            "sources": list[dict],
            "context": str,
            "retrieval_source": str,
            "policy": str,
        }
    """
    chunks = retrieve(question, top_k=top_k)
    context = format_context(chunks)
    sources = format_sources(chunks)
    retrieval_source = chunks[0].get("source", "none") if chunks else "none"

    if not has_enough_evidence(chunks):
        answer = (
            "Tôi không thể xác minh thông tin này từ các nguồn hiện có. "
            "Các đoạn truy xuất được không đủ liên quan để đưa ra câu trả lời có căn cứ."
        )
    else:
        evidence = select_evidence(question, chunks)
        if not evidence:
            answer = (
                "Tôi không thể xác minh thông tin này từ các nguồn hiện có. "
                "Không có câu hoặc đoạn đủ rõ để trích dẫn."
            )
        else:
            lines = ["Dựa trên các nguồn đã truy xuất, câu trả lời có căn cứ như sau:"]
            for item in evidence:
                lines.append(f"- {item['sentence']} [{item['label']}]")
            lines.append(
                "Tôi chỉ sử dụng các đoạn được truy xuất ở trên; nếu cần kết luận pháp lý chính thức, "
                "hãy đối chiếu trực tiếp văn bản gốc."
            )
            answer = "\n".join(lines)

    return {
        "answer": answer,
        "sources": sources,
        "context": context,
        "retrieval_source": retrieval_source,
        "policy": ANTI_HALLUCINATION_POLICY,
    }


def print_answer(question: str, top_k: int = TOP_K) -> None:
    """Small CLI helper for group demos."""
    result = answer_question(question, top_k=top_k)
    print("QUESTION")
    print(question)
    print("\nANSWER")
    print(result["answer"])
    print("\nSOURCES")
    for index, source in enumerate(result["sources"], 1):
        print(f"{index}. {source['label']} | score={source['score']}")
        print(f"   {source['preview']}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print_answer("Hình phạt hoặc quy định liên quan đến ma túy được nêu như thế nào?")
