"""
Task 8 — PageIndex Vectorless RAG.

Khi có PAGEINDEX_API_KEY, có thể thay phần upload/query bằng SDK thật. Bản này
cài local vectorless fallback: tìm kiếm trực tiếp trên cấu trúc markdown corpus,
không dùng embedding/vector store, và luôn đánh dấu source='pageindex'.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .rag_utils import cosine_counter_score, summarize_text, tokenize
from .task4_chunking_indexing import chunk_documents, load_documents


load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).resolve().parent.parent / "data" / "standardized"


def upload_documents() -> list[Path]:
    """Return local markdown files that would be uploaded to PageIndex."""
    return sorted(STANDARDIZED_DIR.rglob("*.md")) if STANDARDIZED_DIR.exists() else []


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval fallback.

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict, 'source': 'pageindex'}
    """
    query_tokens = tokenize(query)
    results = []
    for chunk in chunk_documents(load_documents()):
        score = cosine_counter_score(query_tokens, tokenize(chunk["content"]))
        if score <= 0:
            score = 0.01
        results.append(
            {
                "content": summarize_text(chunk["content"], max_chars=900),
                "score": float(score),
                "metadata": chunk.get("metadata", {}),
                "source": "pageindex",
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    for r in pageindex_search("hình phạt sử dụng ma tuý", top_k=3):
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
