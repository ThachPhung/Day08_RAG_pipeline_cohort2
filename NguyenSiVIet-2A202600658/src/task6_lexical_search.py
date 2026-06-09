"""
Task 6 — Lexical Search Module (BM25).

BM25 hoạt động dựa trên tần suất từ khóa, độ hiếm của từ trong toàn corpus và
chuẩn hóa độ dài document. Bản này tự cài đặt BM25Okapi nhỏ gọn để repo chạy
được ngay cả khi package rank-bm25 chưa được cài.
"""

from __future__ import annotations

import math
from collections import Counter

from .rag_utils import tokenize
from .task4_chunking_indexing import chunk_documents, load_documents


K1 = 1.5
B = 0.75


class SimpleBM25:
    def __init__(self, tokenized_corpus: list[list[str]]):
        self.tokenized_corpus = tokenized_corpus
        self.doc_freqs = [Counter(doc) for doc in tokenized_corpus]
        self.doc_lens = [len(doc) for doc in tokenized_corpus]
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0
        self.idf = self._build_idf()

    def _build_idf(self) -> dict[str, float]:
        n_docs = len(self.tokenized_corpus)
        df: Counter[str] = Counter()
        for doc in self.tokenized_corpus:
            df.update(set(doc))
        return {
            term: math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = []
        for freqs, doc_len in zip(self.doc_freqs, self.doc_lens):
            score = 0.0
            for term in query_tokens:
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                denominator = tf + K1 * (1 - B + B * doc_len / (self.avgdl or 1))
                score += self.idf.get(term, 0.0) * (tf * (K1 + 1)) / denominator
            scores.append(score)
        return scores


def _load_corpus() -> list[dict]:
    return chunk_documents(load_documents())


def build_bm25_index(corpus: list[dict]) -> SimpleBM25:
    """Xây dựng BM25 index từ corpus."""
    return SimpleBM25([tokenize(doc["content"]) for doc in corpus])


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}
        sorted by score descending.
    """
    corpus = _load_corpus()
    if not corpus:
        return []

    bm25 = build_bm25_index(corpus)
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)

    results = []
    for idx, score in ranked[:top_k]:
        if score <= 0:
            continue
        results.append(
            {
                "content": corpus[idx]["content"],
                "score": float(score),
                "metadata": corpus[idx].get("metadata", {}),
            }
        )
    return results


if __name__ == "__main__":
    for r in lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5):
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
