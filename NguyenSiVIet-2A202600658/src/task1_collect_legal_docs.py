"""
Task 1 — Thu thập văn bản pháp luật về ma tuý và các chất cấm.

Hướng dẫn:
    1. Tìm tối thiểu 3 văn bản pháp luật (PDF/DOCX) từ các nguồn chính thống.
    2. Tải về và lưu vào data/landing/legal/.
    3. Đặt tên file rõ ràng, không dấu, có năm ban hành.

Gợi ý nguồn:
    - https://congbao.chinhphu.vn
    - https://vbpl.vn
    - https://thuvienphapluat.vn
    - https://luatvietnam.vn

Gợi ý văn bản:
    - Luật Phòng, chống ma tuý 2021 (73/2021/QH14)
    - Nghị định 105/2021/NĐ-CP
    - Bộ luật Hình sự 2015 (sửa đổi 2017) - Chương XX
    - Nghị định 57/2022/NĐ-CP về danh mục chất ma tuý

Phần bên dưới là script triển khai Task 1: tải 3 PDF từ nguồn chính thống
vào data/landing/legal/ và ghi manifest nguồn để phục vụ citation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import requests


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "landing" / "legal"
MIN_FILE_SIZE = 1024
TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class LegalDocument:
    filename: str
    title: str
    source_url: str
    issuing_body: str
    issued_year: int


LEGAL_DOCUMENTS = [
    LegalDocument(
        filename="luat-phong-chong-ma-tuy-2021.pdf",
        title="Luật Phòng, chống ma tuý 2021 - Luật số 73/2021/QH14",
        source_url=(
            "https://congbao.cdnchinhphu.vn/CongBaoCP/VanBan/2021/3/33659/"
            "35651-1-2021567-56873-2021-qh14.pdf"
        ),
        issuing_body="Quốc hội",
        issued_year=2021,
    ),
    LegalDocument(
        filename="nghi-dinh-105-2021-nd-cp.pdf",
        title=(
            "Nghị định 105/2021/NĐ-CP quy định chi tiết và hướng dẫn thi hành "
            "một số điều của Luật Phòng, chống ma tuý"
        ),
        source_url=(
            "https://congbao.chinhphu.vn/"
            "tai-ve-van-ban-so-105-2021-nd-cp-34944-37821?format=pdf"
        ),
        issuing_body="Chính phủ",
        issued_year=2021,
    ),
    LegalDocument(
        filename="nghi-dinh-57-2022-nd-cp.pdf",
        title="Nghị định 57/2022/NĐ-CP quy định các danh mục chất ma tuý và tiền chất",
        source_url=(
            "https://congbao.chinhphu.vn/"
            "tai-ve-van-ban-so-57-2022-nd-cp-37734-41623?format=pdf"
        ),
        issuing_body="Chính phủ",
        issued_year=2022,
    ),
]


def setup_directory() -> Path:
    """Create data/landing/legal/ if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def download_file(document: LegalDocument, overwrite: bool = False) -> Path:
    """Download one legal document and validate that it is not empty."""
    setup_directory()
    filepath = DATA_DIR / document.filename

    if filepath.exists() and filepath.stat().st_size > MIN_FILE_SIZE and not overwrite:
        print(f"OK existing: {filepath}")
        return filepath

    response = requests.get(
        document.source_url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": "Day08-RAG-Pipeline/1.0"},
    )
    response.raise_for_status()

    content = response.content
    if len(content) <= MIN_FILE_SIZE:
        raise ValueError(
            f"Downloaded file is too small for {document.filename}: {len(content)} bytes"
        )

    filepath.write_bytes(content)
    print(f"Downloaded: {filepath} ({len(content)} bytes)")
    return filepath


def write_manifest(documents: list[LegalDocument]) -> Path:
    """Write source metadata for traceability and later citation."""
    setup_directory()
    manifest_path = DATA_DIR / "legal_sources_manifest.json"
    payload = [asdict(document) for document in documents]
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def collect_legal_documents(overwrite: bool = False) -> list[Path]:
    """Download all Task 1 legal documents."""
    downloaded_files = [
        download_file(document, overwrite=overwrite) for document in LEGAL_DOCUMENTS
    ]
    manifest_path = write_manifest(LEGAL_DOCUMENTS)
    print(f"Manifest: {manifest_path}")
    return downloaded_files


if __name__ == "__main__":
    collect_legal_documents()
