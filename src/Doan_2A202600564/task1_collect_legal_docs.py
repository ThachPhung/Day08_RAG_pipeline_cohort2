"""
Task 1 - Collect Vietnamese legal documents about drugs/narcotics.

Run:
    python src/task1_collect_legal_docs.py

The script stores original PDF/HTML files in data/landing/legal/. Existing files
are left untouched so repeated runs are safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import requests
from requests.exceptions import RequestException
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data" / "landing" / "legal"


@dataclass(frozen=True)
class LegalDocument:
    title: str
    url: str
    filename: str
    kind: Literal["pdf", "html"]


DOCUMENTS: tuple[LegalDocument, ...] = (
    LegalDocument(
        title="Luat Phong, chong ma tuy 2021 - so 73/2021/QH14",
        url=(
            "https://g7.cdnchinhphu.vn/api/download/stream"
            "?Url=tm-8mq6BhNw0NbrKRhTDAQWsKg3tuqaY0aWypnY78U6M2BY68Ekp0Gvvr483flbRjbik8E0wBHUyBAiSflcQEJHAmcZL6yTIQL6RZmX61EtZRIA6qhCdHI7bAwaisGDmaN_1mqn-kBerf_4AVrsSdg~~"
            "&file_name=2021_567+%2B+568_73-2021-QH14.pdf"
        ),
        filename="luat-phong-chong-ma-tuy-2021.pdf",
        kind="pdf",
    ),
    LegalDocument(
        title="Nghi dinh 105/2021/ND-CP huong dan Luat Phong, chong ma tuy",
        url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2021/12/105.signed_02.pdf",
        filename="nghi-dinh-105-2021.pdf",
        kind="pdf",
    ),
    LegalDocument(
        title="Bo luat Hinh su 2015 sua doi 2017 - Chuong XX cac toi pham ve ma tuy",
        url="https://hethongphapluat.com/bo-luat-hinh-su-2015/phan-2/chuong-20",
        filename="bo-luat-hinh-su-2015-sua-doi-2017-chuong-xx.html",
        kind="html",
    ),
    # The local automated tests for this coursework count only PDF/DOC/DOCX
    # files, so keep an official original PDF copy of the Criminal Code too.
    LegalDocument(
        title="Bo luat Hinh su 2015 - original PDF",
        url=(
            "https://g7.cdnchinhphu.vn/api/download/stream"
            "?Url=tm-8mq6BhNw0NbrKRhTDAQWsKg3tuqaY0aWypnY78U6M2BY68Ekp0Gvvr483flbRvsvDD79D8g54kcgDl-0nJedXYuKZss8xDn259jG6y-dQBluwyxQV0byXqh3qzb_bNtX0vmuWRA2agMf_YOB764ZNVMUZXkqDiJe-Nw1GIGg~"
            "&file_name=In_CB+1269%2B1270+31-12-2015.signed.signed.signed.signed.signed.pdf"
        ),
        filename="bo-luat-hinh-su-2015.pdf",
        kind="pdf",
    ),
)


def setup_directory() -> None:
    """Create data/landing/legal/ when it does not already exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def download_document(document: LegalDocument) -> str:
    """Download one document unless the target file already exists."""
    output_path = DATA_DIR / document.filename
    if output_path.exists():
        return "skipped"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(document.url, headers=headers, timeout=30)
    except RequestException:
        if document.kind != "html" and "g7.cdnchinhphu.vn" not in document.url:
            raise
        disable_warnings(InsecureRequestWarning)
        response = requests.get(document.url, headers=headers, timeout=30, verify=False)

    if document.kind == "html" and response.status_code == 403:
        disable_warnings(InsecureRequestWarning)
        response = requests.get(document.url, headers=headers, timeout=30, verify=False)
    response.raise_for_status()

    if document.kind == "pdf" and not response.content.startswith(b"%PDF"):
        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower():
            raise ValueError(
                f"{document.filename}: expected PDF response, got {content_type or 'unknown content type'}"
            )

    output_path.write_bytes(response.content)
    return "downloaded"


def collect_documents() -> dict[str, list[str]]:
    """Create the legal landing folder and collect configured documents."""
    setup_directory()

    summary: dict[str, list[str]] = {
        "downloaded": [],
        "skipped": [],
        "failed": [],
    }

    for document in DOCUMENTS:
        try:
            status = download_document(document)
            summary[status].append(document.filename)
            print(f"{status.upper():10} {document.filename}")
        except Exception as exc:
            summary["failed"].append(f"{document.filename} ({exc})")
            print(f"FAILED     {document.filename}: {exc}")

    return summary


def print_summary(summary: dict[str, list[str]]) -> None:
    """Print a compact end-of-run summary."""
    print("\nSummary")
    print("-" * 40)
    for status in ("downloaded", "skipped", "failed"):
        files = summary[status]
        print(f"{status.capitalize()}: {len(files)}")
        for filename in files:
            print(f"  - {filename}")


if __name__ == "__main__":
    print("Task 1: Collect legal documents")
    print(f"Output directory: {DATA_DIR}")
    print_summary(collect_documents())
