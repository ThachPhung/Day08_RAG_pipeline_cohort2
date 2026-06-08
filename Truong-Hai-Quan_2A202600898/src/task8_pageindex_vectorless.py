"""
Task 8 — PageIndex Vectorless RAG (https://pageindex.ai).

PageIndex = RAG "vectorless": thay vì embedding, nó OCR tài liệu rồi dựng CÂY
cấu trúc (tree) gồm các node Chương/Điều/Khoản kèm text. Truy hồi = để LLM
"reasoning" duyệt cây chọn node liên quan (không cần vector). Rất hợp làm
FALLBACK cho văn bản luật scan — PageIndex tự OCR phía server.

API thật (https://api.pageindex.ai, header `api_key`):
    Upload : POST /doc/                      (multipart 'file'=PDF) -> {doc_id}
    Status : GET  /doc/{doc_id}/             -> {status, retrieval_ready, ...}
    Tree   : GET  /doc/{doc_id}/?type=tree   -> cây node có 'text' (OCR)
    (Endpoint /retrieval/ cũ đã DEPRECATED → ở đây dùng tree + LLM tree-search.)

Quy trình:
    upload_documents()  → đẩy PDF luật, chờ xử lý xong (OCR + tree), lưu doc_id.
    pageindex_search()  → lấy tree (cache) → LLM chọn node liên quan → trả chunk.

Thiếu PAGEINDEX_API_KEY / chưa upload → trả [] (không raise) để pipeline fallback
không vỡ và test skip sạch.
"""

import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.rag_common import _force_utf8_stdout

load_dotenv()
_force_utf8_stdout()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
BASE_URL = "https://api.pageindex.ai"
SELECT_MODEL = "gpt-4o-mini"

LEGAL_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
INDEX_DIR = Path(__file__).parent.parent / "data" / "index"
DOCS_STORE = INDEX_DIR / "pageindex_docs.json"      # {filename: doc_id}
TREES_DIR = INDEX_DIR / "pageindex_trees"            # cache cây mỗi doc


def _headers() -> dict:
    return {"api_key": PAGEINDEX_API_KEY}


def _is_done(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in ("complet", "success", "done", "ready", "finish"))


def _is_failed(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in ("fail", "error"))


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
def _submit_pdf(path: Path) -> str:
    with open(path, "rb") as f:
        resp = requests.post(
            f"{BASE_URL}/doc/",
            headers=_headers(),
            files={"file": (path.name, f, "application/pdf")},
            timeout=180,
        )
    resp.raise_for_status()
    return resp.json()["doc_id"]


def _wait_doc(doc_id: str, timeout: int = 900, interval: int = 8) -> bool:
    """Poll tới khi document xử lý xong (OCR + tree). status='completed' là đủ."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/doc/{doc_id}/", headers=_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status") or data.get("state") or ""
        if data.get("retrieval_ready") is True or _is_done(status):
            return True
        if _is_failed(status):
            print(f"  ✗ Xử lý lỗi (doc_id={doc_id}, status={status})")
            return False
        time.sleep(interval)
    print(f"  ✗ Hết thời gian chờ xử lý doc_id={doc_id}")
    return False


def upload_documents() -> dict:
    """Upload các PDF luật lên PageIndex (tự OCR), lưu mapping {filename: doc_id}."""
    if not PAGEINDEX_API_KEY:
        print("⚠ Thiếu PAGEINDEX_API_KEY trong .env — bỏ qua upload.")
        return {}

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store: dict = {}
    if DOCS_STORE.exists():
        store = json.loads(DOCS_STORE.read_text(encoding="utf-8"))

    for pdf in sorted(LEGAL_DIR.glob("*.pdf")):
        if pdf.name in store:
            print(f"• Đã có doc_id cho {pdf.name}, bỏ qua.")
            continue
        print(f"Uploading: {pdf.name} ...")
        try:
            doc_id = _submit_pdf(pdf)
            print(f"  → doc_id={doc_id}, chờ xử lý (OCR + tree)...")
            if _wait_doc(doc_id):
                store[pdf.name] = doc_id
                DOCS_STORE.write_text(
                    json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"  ✓ Xong: {pdf.name}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ Lỗi upload {pdf.name}: {e}")

    print(f"\n✓ PageIndex store: {len(store)} document → {DOCS_STORE}")
    return store


# ---------------------------------------------------------------------------
# Tree (cache) + flatten
# ---------------------------------------------------------------------------
def _fetch_tree(doc_id: str) -> list:
    """Lấy cây node của 1 doc (cache ra đĩa để khỏi gọi lại)."""
    TREES_DIR.mkdir(parents=True, exist_ok=True)
    cache = TREES_DIR / f"{doc_id}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    r = requests.get(f"{BASE_URL}/doc/{doc_id}/?type=tree", headers=_headers(), timeout=60)
    r.raise_for_status()
    tree = r.json().get("result") or r.json().get("tree") or []
    cache.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    return tree


_IDX_TAG = re.compile(r"<physical_index_\d+>|</physical_index_\d+>")


def _clean(text: str) -> str:
    return _IDX_TAG.sub("", text or "").strip()


def _flatten(nodes, source: str, out: list):
    """Duyệt đệ quy cây, gom node có 'text' (OCR) → list phẳng."""
    if isinstance(nodes, str):
        return
    for n in nodes or []:
        if not isinstance(n, dict):
            continue
        text = _clean(n.get("text", ""))
        if len(text) > 30:
            out.append(
                {
                    "node_id": n.get("node_id"),
                    "title": n.get("title", ""),
                    "page_index": n.get("page_index"),
                    "text": text,
                    "source": source,
                }
            )
        _flatten(n.get("nodes"), source, out)


def _all_nodes() -> list[dict]:
    """Gom toàn bộ node (có text) của mọi doc đã upload."""
    if not DOCS_STORE.exists():
        return []
    try:
        store = json.loads(DOCS_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []
    nodes: list[dict] = []
    for filename, doc_id in store.items():
        try:
            _flatten(_fetch_tree(doc_id), filename, nodes)
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠ Lỗi lấy tree ({filename}): {e}")
    return nodes


# ---------------------------------------------------------------------------
# Vectorless tree-search bằng LLM
# ---------------------------------------------------------------------------
def _select_nodes(query: str, nodes: list[dict], top_k: int) -> list[int]:
    """Cho LLM đọc danh sách (tiêu đề + trích đoạn) → trả index node liên quan nhất."""
    from src.rag_common import _openai_client

    listing = "\n".join(
        f"{i}. [{n['source'][:18]}] {n['title']} :: {n['text'][:90]}"
        for i, n in enumerate(nodes)
    )
    prompt = (
        f"Câu hỏi: {query}\n\n"
        f"Danh sách các mục tài liệu pháp luật (index. [nguồn] tiêu đề :: trích đoạn):\n"
        f"{listing}\n\n"
        f"Chọn tối đa {top_k} mục LIÊN QUAN NHẤT để trả lời câu hỏi. "
        f"Chỉ trả về JSON là mảng các số index, ví dụ [3, 0, 7]."
    )
    resp = _openai_client().with_options(timeout=60).chat.completions.create(
        model=SELECT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "Bạn chọn mục tài liệu liên quan, chỉ trả JSON mảng số."},
            {"role": "user", "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content or "[]"
    m = re.search(r"\[[\d,\s]*\]", raw)
    try:
        idxs = json.loads(m.group(0)) if m else []
    except Exception:
        idxs = []
    return [i for i in idxs if isinstance(i, int) and 0 <= i < len(nodes)][:top_k]


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval qua PageIndex tree + LLM tree-search.

    Returns:
        List of {content, score, metadata, source:'pageindex'}, theo độ liên quan.
        Trả [] nếu thiếu key / chưa upload / lỗi (không raise).
    """
    if not PAGEINDEX_API_KEY:
        return []

    nodes = _all_nodes()
    if not nodes:
        return []

    try:
        chosen = _select_nodes(query, nodes, top_k)
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ PageIndex tree-search lỗi: {e}")
        return []

    results = []
    for rank, idx in enumerate(chosen):
        n = nodes[idx]
        results.append(
            {
                "content": n["text"],
                "score": round(1.0 - rank * 0.1, 3),  # điểm theo thứ hạng LLM chọn
                "metadata": {
                    "source": n["source"],
                    "doc_type": "legal",
                    "node_id": n["node_id"],
                    "page_index": n["page_index"],
                },
                "source": "pageindex",
            }
        )
    return results


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong .env (đăng ký tại https://pageindex.ai/)")
    else:
        upload_documents()
        print("\nTest query:")
        for r in pageindex_search("Quy định về cai nghiện ma tuý bắt buộc", top_k=3):
            print(f"[{r['score']:.2f}] ({r['metadata']['source'][:25]}) {r['content'][:90]}...")
