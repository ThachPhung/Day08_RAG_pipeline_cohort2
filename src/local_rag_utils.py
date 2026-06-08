from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)


def load_markdown_documents() -> list[dict]:
    documents = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
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


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        end = min(len(text), start + chunk_size)
        window = text[start:end]
        if end < len(text):
            split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "), window.rfind(" "))
            if split_at > chunk_size * 0.5:
                end = start + split_at + 1
                window = text[start:end]
        chunks.append(window.strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
        if start < len(chunks) * step * 0.25:
            start = end
    return [chunk for chunk in chunks if chunk]


def chunk_documents(documents: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    chunks = []
    for doc in documents:
        for index, chunk in enumerate(split_text(doc["content"], chunk_size, overlap)):
            chunks.append(
                {
                    "content": chunk,
                    "metadata": {**doc.get("metadata", {}), "chunk_index": index},
                }
            )
    return chunks


def simple_embedding(text: str, dim: int = 128) -> list[float]:
    vector = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def semantic_rank(query: str, chunks: list[dict], top_k: int = 10) -> list[dict]:
    query_embedding = simple_embedding(query)
    results = []
    for chunk in chunks:
        score = cosine_similarity(query_embedding, simple_embedding(chunk["content"]))
        results.append({**chunk, "score": float(score)})
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def lexical_rank(query: str, chunks: list[dict], top_k: int = 10) -> list[dict]:
    query_terms = tokenize(query)
    if not query_terms:
        return []

    tokenized_docs = [tokenize(chunk["content"]) for chunk in chunks]
    doc_count = len(tokenized_docs) or 1
    avg_len = sum(len(doc) for doc in tokenized_docs) / doc_count if tokenized_docs else 1.0
    dfs = Counter(term for doc in tokenized_docs for term in set(doc))
    k1 = 1.5
    b = 0.75

    results = []
    for chunk, terms in zip(chunks, tokenized_docs):
        counts = Counter(terms)
        doc_len = len(terms) or 1
        score = 0.0
        for term in query_terms:
            if counts[term] == 0:
                continue
            idf = math.log(1 + (doc_count - dfs[term] + 0.5) / (dfs[term] + 0.5))
            numerator = counts[term] * (k1 + 1)
            denominator = counts[term] + k1 * (1 - b + b * doc_len / avg_len)
            score += idf * numerator / denominator
        results.append({**chunk, "score": float(score)})

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
