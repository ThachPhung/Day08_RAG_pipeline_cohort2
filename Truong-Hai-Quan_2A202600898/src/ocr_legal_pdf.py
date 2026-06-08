"""
OCR các PDF luật dạng SCAN (ảnh) → text, dùng OpenAI vision (gpt-4o-mini).

Vì sao cần: 3 file luật (luat120-2025, ND28-2026, 105.signed...) là PDF scan,
không có lớp text → MarkItDown bóc ra rỗng. Module này render từng trang bằng
PyMuPDF rồi nhờ gpt-4o-mini đọc lại chữ tiếng Việt (giữ Điều/Khoản, bảng, dấu).

Output: data/standardized/legal/<tên>.md  → tự động vào hybrid index (Task 4) và
BM25 cục bộ (Task 6).

Chạy:
    python -m src.ocr_legal_pdf
"""

import base64
import concurrent.futures as cf
from pathlib import Path

import fitz  # PyMuPDF

from src.rag_common import _force_utf8_stdout, _openai_client

_force_utf8_stdout()

LEGAL_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized" / "legal"

OCR_MODEL = "gpt-4o-mini"
RENDER_DPI = 130           # đủ nét; vision tự downscale nên không cần cao hơn
MAX_WORKERS = 2            # giữ thấp để không vượt TPM 200k (ảnh high-detail tốn token)
CALL_TIMEOUT = 120         # giây — chặn 1 trang treo quá lâu giữ luồng
MAX_RETRIES = 10           # để SDK tự backoff khi gặp 429 (honor Retry-After)
CHARS_PER_PAGE_MIN = 50    # trung bình < ngần này ký tự/trang ⇒ là PDF scan, cần OCR

OCR_SYSTEM = "Bạn là công cụ OCR tiếng Việt chính xác cho văn bản pháp luật."
OCR_PROMPT = (
    "Chép lại CHÍNH XÁC toàn bộ chữ tiếng Việt trong ảnh trang tài liệu pháp luật này. "
    "Giữ nguyên số Điều/Khoản/Điểm, dấu tiếng Việt, và chuyển bảng thành text có cấu trúc "
    "(mỗi dòng một mục). Chỉ xuất nội dung văn bản, KHÔNG thêm lời bình. "
    "Nếu trang trống hoặc không đọc được, trả về chuỗi rỗng."
)


def _needs_ocr(pdf: Path) -> bool:
    """True nếu PDF gần như không có lớp text (là bản scan)."""
    doc = fitz.open(str(pdf))
    chars = sum(len(p.get_text()) for p in doc)
    pages = max(doc.page_count, 1)
    doc.close()
    return (chars / pages) < CHARS_PER_PAGE_MIN


def _pages_in_md(pdf: Path) -> dict[int, str]:
    """
    Đọc các trang ĐÃ OCR từ .md hiện có → {page_no: text}. Dùng làm 'cache' để
    re-run chỉ OCR các trang còn thiếu (chống mất trang do rate limit 429).
    """
    import re

    md = OUTPUT_DIR / f"{pdf.stem}.md"
    if not md.exists():
        return {}
    txt = md.read_text(encoding="utf-8")
    out: dict[int, str] = {}
    matches = list(re.finditer(r"\[Trang (\d+)\]\n", txt))
    for idx, m in enumerate(matches):
        page = int(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(txt)
        body = txt[start:end].strip()
        if body:
            out[page] = body
    return out


def _page_png_b64(pdf_path: str, page_no: int) -> str:
    """Render 1 trang thành PNG (base64). Mở/đóng doc cục bộ để thread-safe."""
    doc = fitz.open(pdf_path)
    pix = doc[page_no].get_pixmap(dpi=RENDER_DPI)
    png = pix.tobytes("png")
    doc.close()
    return base64.b64encode(png).decode("ascii")


def _ocr_page(pdf_path: str, page_no: int) -> str:
    """OCR 1 trang qua OpenAI vision; retry 1 lần khi lỗi."""
    b64 = _page_png_b64(pdf_path, page_no)
    client = _openai_client().with_options(timeout=CALL_TIMEOUT, max_retries=MAX_RETRIES)
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=OCR_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": OCR_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001
            if attempt == 1:
                print(f"    ✗ Trang {page_no + 1} lỗi OCR: {e}")
                return ""
    return ""


def ocr_pdf(pdf: Path) -> int:
    """
    OCR (gap-filling) 1 PDF → ghi .md. Giữ nguyên trang đã OCR, chỉ làm trang
    thiếu. Trả về SỐ TRANG CÒN THIẾU sau lượt này (0 = xong hẳn).
    """
    doc = fitz.open(str(pdf))
    n = doc.page_count
    doc.close()

    results = _pages_in_md(pdf)  # các trang đã có
    missing = [p for p in range(1, n + 1) if p not in results]
    if not missing:
        print(f"• {pdf.name}: đủ {n}/{n} trang, bỏ qua.")
        return 0

    print(f"OCR {pdf.name} — thiếu {len(missing)}/{n} trang, làm tiếp (song song {MAX_WORKERS})...")
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_ocr_page, str(pdf), p - 1): p for p in missing}
        done = 0
        for fut in cf.as_completed(futs):
            p = futs[fut]
            text = fut.result()
            if text:
                results[p] = text
            done += 1
            if done % 5 == 0 or done == len(missing):
                print(f"  …{done}/{len(missing)} trang (đã có tổng {len(results)}/{n})")

    body = "\n\n".join(f"[Trang {p}]\n{results[p]}" for p in sorted(results))
    header = f"# {pdf.stem}\n\n**Nguồn:** {pdf.name} (legal, OCR vision)\n\n---\n\n"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{pdf.stem}.md").write_text(header + body, encoding="utf-8")

    still = [p for p in range(1, n + 1) if p not in results]
    print(f"  ✓ Saved: {pdf.stem}.md — {len(results)}/{n} trang. Còn thiếu {len(still)}: {still[:15]}")
    return len(still)


def run(force: bool = False):
    """
    OCR (gap-filling) mọi PDF scan trong landing/legal. Idempotent: chạy lại chỉ
    làm trang còn thiếu → có thể chạy nhiều lượt cho tới khi 'Còn thiếu 0'.
    force=True để xét cả PDF có lớp text.
    """
    print("=" * 50)
    print("OCR Legal PDFs (OpenAI vision) — resumable / gap-filling")
    print("=" * 50)
    pdfs = sorted(LEGAL_DIR.glob("*.pdf"))
    targets = [p for p in pdfs if force or _needs_ocr(p)]
    if not targets:
        print("Không có PDF scan nào cần OCR.")
        return

    total_missing = 0
    for pdf in targets:
        total_missing += ocr_pdf(pdf)

    if total_missing == 0:
        print("\n✓ OCR hoàn tất 100% các trang. Chạy lại Task 4 để index.")
    else:
        print(f"\n⚠ Còn {total_missing} trang thiếu (do rate limit). Chạy lại lệnh này để làm nốt.")


if __name__ == "__main__":
    run()
