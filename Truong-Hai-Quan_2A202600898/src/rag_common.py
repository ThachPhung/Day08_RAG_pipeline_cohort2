"""
rag_common — Hạ tầng dùng chung cho toàn bộ pipeline RAG (Task 4–10).

Gom các thứ tái sử dụng vào một chỗ:
    - Đường dẫn chuẩn của project
    - OpenAI client + hàm embedding (text-embedding-3-small, 1536 dim)
    - Vector store = Weaviate Cloud (hybrid search built-in: dense + BM25)
    - Tokenizer tiếng Việt đơn giản

Vì sao Weaviate?
    Weaviate hỗ trợ HYBRID SEARCH built-in (vector near_vector + BM25 lexical +
    hybrid fusion) ngay trong DB — đúng "chuẩn" production. Ở đây dùng Weaviate
    Cloud (sandbox free) để khỏi cần Docker, chạy được trên Windows.

    Embedding do TA tự tính bằng OpenAI rồi nạp vector vào Weaviate
    (vectorizer = self_provided). Cách này giữ toàn quyền kiểm soát model
    embedding và dễ bê nguyên sang product thật.

Cấu hình (.env):
    WEAVIATE_URL=https://<cluster-id>.weaviate.cloud
    WEAVIATE_API_KEY=<api-key>
    OPENAI_API_KEY=sk-...
"""

from __future__ import annotations

import atexit
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional
    pass


def _force_utf8_stdout() -> None:
    """Windows console mặc định cp1252 → in ✓/✗/tiếng Việt bị lỗi. Ép UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


_force_utf8_stdout()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
LANDING_DIR = DATA_DIR / "landing"
STANDARDIZED_DIR = DATA_DIR / "standardized"

# ---------------------------------------------------------------------------
# Embedding config (OpenAI)
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


@lru_cache(maxsize=1)
def _openai_client():
    """Khởi tạo OpenAI client 1 lần (cần OPENAI_API_KEY)."""
    from openai import OpenAI

    return OpenAI()


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    Embed danh sách text bằng OpenAI. Trả về list vector (mỗi vector dài
    EMBEDDING_DIM), đã chuẩn hoá L2 để cosine = dot product.
    """
    if not texts:
        return []

    client = _openai_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [t.replace("\n", " ")[:8000] for t in texts[i : i + batch_size]]
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        for d in resp.data:
            v = np.asarray(d.embedding, dtype=np.float32)
            n = float(np.linalg.norm(v)) or 1.0
            out.append((v / n).tolist())
    return out


def embed_query(query: str) -> list[float]:
    """Embed 1 query → vector đã chuẩn hoá."""
    return embed_texts([query])[0]


# ---------------------------------------------------------------------------
# Vector store = Weaviate Cloud
# ---------------------------------------------------------------------------
COLLECTION_NAME = "DrugLawDocs"


def _creds() -> tuple[str, str]:
    url = os.environ.get("WEAVIATE_URL", "").strip()
    key = os.environ.get("WEAVIATE_API_KEY", "").strip()
    if not url or not key:
        raise RuntimeError(
            "Chưa cấu hình WEAVIATE_URL / WEAVIATE_API_KEY trong .env. "
            "Xem hướng dẫn tạo Weaviate Cloud sandbox ở README."
        )
    return url, key


@lru_cache(maxsize=1)
def get_client():
    """
    Kết nối Weaviate Cloud (cache 1 connection cho cả process, tự đóng khi thoát).
    """
    import weaviate
    from weaviate.classes.init import Auth

    url, key = _creds()
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=url,
        auth_credentials=Auth.api_key(key),
    )
    atexit.register(_close_client)
    return client


def _close_client():
    try:
        if get_client.cache_info().currsize:  # type: ignore[attr-defined]
            get_client().close()
    except Exception:
        pass


def is_ready() -> bool:
    """True nếu kết nối được Weaviate (đã cấu hình + cluster sống)."""
    try:
        return bool(get_client().is_ready())
    except Exception:
        return False


def create_collection(reset: bool = True):
    """
    Tạo collection DrugLawDocs với self-provided vectors + BM25 inverted index.
    reset=True sẽ xoá collection cũ để index lại từ đầu.
    """
    from weaviate.classes.config import Configure, DataType, Property

    client = get_client()
    if reset and client.collections.exists(COLLECTION_NAME):
        client.collections.delete(COLLECTION_NAME)

    if not client.collections.exists(COLLECTION_NAME):
        client.collections.create(
            name=COLLECTION_NAME,
            # TA tự nạp vector (đã embed bằng OpenAI) → self_provided
            vector_config=Configure.Vectors.self_provided(),
            properties=[
                Property(name="content", data_type=DataType.TEXT),
                Property(name="source", data_type=DataType.TEXT),
                Property(name="doc_type", data_type=DataType.TEXT),
                Property(name="chunk_index", data_type=DataType.INT),
            ],
        )
    return client.collections.get(COLLECTION_NAME)


def get_collection():
    """Lấy collection nếu tồn tại, ngược lại None."""
    try:
        client = get_client()
        if client.collections.exists(COLLECTION_NAME):
            return client.collections.get(COLLECTION_NAME)
    except Exception:
        pass
    return None


def index_count() -> int:
    """Số object đang có trong collection (0 nếu chưa index / chưa kết nối)."""
    col = get_collection()
    if col is None:
        return 0
    try:
        return col.aggregate.over_all(total_count=True).total_count or 0
    except Exception:
        return 0


def index_exists() -> bool:
    return index_count() > 0


# ---------------------------------------------------------------------------
# Tokenizer tiếng Việt (đơn giản)
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[0-9a-zà-ỹ]+", re.UNICODE)


def tokenize_vi(text: str) -> list[str]:
    """Tách token theo word, lowercase, giữ chữ có dấu tiếng Việt và chữ số."""
    return _WORD_RE.findall(text.lower())
