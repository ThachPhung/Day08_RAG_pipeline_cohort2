"""
Shared index store for Tasks 4–6 (local pickle, no external DB required).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_DIR = Path(__file__).parent.parent
INDEX_DIR = PROJECT_DIR / "data" / "index"
CHUNKS_PATH = INDEX_DIR / "chunks.pkl"
BM25_PATH = INDEX_DIR / "bm25.pkl"

_embedding_model = None
_bm25_state: dict[str, Any] | None = None
_chunks_cache: list[dict] | None = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        from src.task4_chunking_indexing import EMBEDDING_MODEL

        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def embed_texts(texts: list[str]) -> np.ndarray:
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(embeddings, dtype=np.float32)


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


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

    from src.task4_chunking_indexing import (
        chunk_documents,
        embed_chunks,
        index_to_vectorstore,
        load_documents,
    )

    docs = load_documents()
    if not docs:
        return []
    chunks = chunk_documents(docs)
    chunks = embed_chunks(chunks)
    index_to_vectorstore(chunks)
    return load_chunks()


def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return matrix @ query_vec


def tokenize(text: str) -> list[str]:
    return text.lower().split()


def get_bm25_state() -> dict[str, Any]:
    global _bm25_state
    if _bm25_state is not None:
        return _bm25_state

    if BM25_PATH.exists():
        with BM25_PATH.open("rb") as f:
            _bm25_state = pickle.load(f)
        return _bm25_state

    from rank_bm25 import BM25Okapi

    chunks = ensure_index()
    corpus = [tokenize(c["content"]) for c in chunks]
    bm25 = BM25Okapi(corpus)
    _bm25_state = {"bm25": bm25, "chunks": chunks}
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with BM25_PATH.open("wb") as f:
        pickle.dump(_bm25_state, f)
    return _bm25_state
