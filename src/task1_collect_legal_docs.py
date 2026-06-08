"""
Task 1 - Thu thap van ban phap luat ve ma tuy va cac chat cam.

Chon 3 van ban:
    1. Luat Phong, chong ma tuy 2021.
    2. Nghi dinh 105/2021/ND-CP.
    3. Nghi dinh 57/2022/ND-CP ve danh muc chat ma tuy va tien chat.
"""

from pathlib import Path
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

LEGAL_DOCS = {
    "luat-phong-chong-ma-tuy-2021.pdf": "https://congan.sonla.gov.vn/wp-content/uploads/2022/05/1.-Luat-PCMT-2021.pdf",
    "nghi-dinh-105-2021.pdf": "https://congbao.cdnchinhphu.vn/CongBaoCP/VanBan/2021/12/34944/37821-1-20211047-1048105-2021-nd-cp.pdf",
    "nghi-dinh-57-2022.pdf": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2022/8/37734/41623-1-2022709-71057-2022-nd-cp.pdf",
}


def setup_directory() -> None:
    """Create data/landing/legal/ if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Legal landing directory ready: {DATA_DIR}")


def download_file(url: str, filename: str) -> Path:
    """Download one legal document into data/landing/legal/."""
    setup_directory()
    filepath = DATA_DIR / filename
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        filepath.write_bytes(response.read())
    print(f"Downloaded: {filepath}")
    return filepath


def download_all() -> list[Path]:
    """Download all selected legal documents for Task 1."""
    return [download_file(url, filename) for filename, url in LEGAL_DOCS.items()]


if __name__ == "__main__":
    download_all()
