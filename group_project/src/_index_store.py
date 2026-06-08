"""Local index utilities for the group RAG pipeline.

The group pipeline keeps generated artifacts inside group_project/index so it
does not overwrite individual task outputs.
"""

from __future__ import annotations

import hashlib
import math
import os
import pickle
import re
from pathlib import Path
from typing import Any

import numpy as np

GROUP_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = GROUP_DIR.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
INDEX_DIR = GROUP_DIR / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.pkl"
BM25_PATH = INDEX_DIR / "bm25.pkl"

EMBEDDING_MODEL = "hashing-384-offline"
SENTENCE_TRANSFORMERS_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

_embedding_model = None
_model_failed = False
_chunks_cache: list[dict] | None = None
_bm25_state: dict[str, Any] | None = None


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower(), flags=re.UNICODE) if len(t) > 1]


def _hash_embed(texts: list[str]) -> np.ndarray:
    vectors = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
    for row, text in enumerate(texts):
        for token in tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vectors[row, idx] += sign
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def get_embedding_model():
    global _embedding_model, _model_failed
    if os.getenv("GROUP_RAG_USE_SENTENCE_TRANSFORMERS") != "1":
        return None
    if _model_failed:
        return None
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(SENTENCE_TRANSFORMERS_MODEL)
        except Exception:
            _model_failed = True
            return None
    return _embedding_model


def embed_texts(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()
    if model is None:
        return _hash_embed(texts)
    try:
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(embeddings, dtype=np.float32)
    except Exception:
        return _hash_embed(texts)


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return matrix @ query_vec


def save_chunks(chunks: list[dict]) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("wb") as f:
        pickle.dump(chunks, f)
    global _chunks_cache, _bm25_state
    _chunks_cache = chunks
    _bm25_state = None


def load_chunks() -> list[dict]:
    global _chunks_cache
    if _chunks_cache is not None:
        return _chunks_cache
    if not CHUNKS_PATH.exists():
        return []
    with CHUNKS_PATH.open("rb") as f:
        _chunks_cache = pickle.load(f)
    return _chunks_cache


def ensure_index() -> list[dict]:
    chunks = load_chunks()
    if chunks:
        return chunks

    from group_project.src.task4_chunking_indexing import (
        chunk_documents,
        embed_chunks,
        index_to_vectorstore,
        load_documents,
    )

    docs = load_documents()
    if not docs:
        return []
    chunks = embed_chunks(chunk_documents(docs))
    index_to_vectorstore(chunks)
    return load_chunks()


class SimpleBM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.avgdl = sum(len(doc) for doc in corpus) / max(len(corpus), 1)
        self.doc_freq: dict[str, int] = {}
        self.term_freqs: list[dict[str, int]] = []
        for doc in corpus:
            tf: dict[str, int] = {}
            for token in doc:
                tf[token] = tf.get(token, 0) + 1
            self.term_freqs.append(tf)
            for token in tf:
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1

    def get_scores(self, query_tokens: list[str]) -> np.ndarray:
        n_docs = len(self.corpus)
        scores = np.zeros(n_docs, dtype=np.float32)
        for token in query_tokens:
            df = self.doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for i, doc in enumerate(self.corpus):
                freq = self.term_freqs[i].get(token, 0)
                if freq == 0:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * len(doc) / max(self.avgdl, 1))
                scores[i] += idf * freq * (self.k1 + 1) / denom
        return scores


def get_bm25_state() -> dict[str, Any]:
    global _bm25_state
    if _bm25_state is not None:
        return _bm25_state
    if BM25_PATH.exists():
        with BM25_PATH.open("rb") as f:
            _bm25_state = pickle.load(f)
        return _bm25_state

    chunks = ensure_index()
    corpus = [tokenize(c["content"]) for c in chunks]
    try:
        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi(corpus)
    except Exception:
        bm25 = SimpleBM25(corpus)

    _bm25_state = {"bm25": bm25, "chunks": chunks}
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with BM25_PATH.open("wb") as f:
        pickle.dump(_bm25_state, f)
    return _bm25_state
