"""Small local utilities shared by the individual RAG tasks."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"


def tokenize(text: str) -> list[str]:
    """Tokenize Vietnamese/ASCII text with a simple Unicode-aware regex."""
    return re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE)


def load_markdown_documents() -> list[dict]:
    """Load standardized markdown files as RAG documents."""
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            continue
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "path": str(md_file.relative_to(PROJECT_DIR)),
                    "type": doc_type,
                },
            }
        )
    return documents


def cosine_counter_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Cosine similarity over token-count vectors."""
    if not query_tokens or not doc_tokens:
        return 0.0

    q_counts = Counter(query_tokens)
    d_counts = Counter(doc_tokens)
    dot = sum(q_counts[token] * d_counts.get(token, 0) for token in q_counts)
    q_norm = math.sqrt(sum(value * value for value in q_counts.values()))
    d_norm = math.sqrt(sum(value * value for value in d_counts.values()))
    if q_norm == 0 or d_norm == 0:
        return 0.0
    return dot / (q_norm * d_norm)


def summarize_text(text: str, max_chars: int = 800) -> str:
    """Return a compact context snippet without cutting too aggressively."""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."
