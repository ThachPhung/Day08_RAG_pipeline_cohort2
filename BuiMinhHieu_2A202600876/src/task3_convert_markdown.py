"""
Task 3 - Convert landing files to Markdown.

For news JSON files we preserve the crawled markdown content. For legal PDF/DOC
files, we use Microsoft MarkItDown when available and keep a small fallback so
the pipeline remains runnable if one document cannot be parsed.
"""

import json
from pathlib import Path

try:
    from markitdown import MarkItDown
except Exception:  # pragma: no cover - fallback path for minimal environments
    MarkItDown = None

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"

LEGAL_SUMMARIES = {
    "luat-phong-chong-ma-tuy-2021": (
        "Luat Phong, chong ma tuy 2021 quy dinh trach nhiem phong, chong ma tuy, "
        "quan ly nguoi su dung trai phep chat ma tuy, cai nghien ma tuy va cac "
        "bien phap ho tro tai hoa nhap cong dong."
    ),
    "nghi-dinh-105-2021": (
        "Nghi dinh 105/2021/ND-CP quy dinh chi tiet va huong dan thi hanh mot so "
        "dieu cua Luat Phong, chong ma tuy, bao gom phoi hop cua cac co quan "
        "chuyen trach va kiem soat hoat dong hop phap lien quan den ma tuy."
    ),
    "nghi-dinh-57-2022": (
        "Nghi dinh 57/2022/ND-CP quy dinh cac danh muc chat ma tuy va tien chat, "
        "lam co so phap ly de nhan dien, quan ly va kiem soat cac chat cam."
    ),
}


def convert_legal_docs() -> list[Path]:
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    converter = MarkItDown() if MarkItDown is not None else None

    for filepath in legal_dir.iterdir():
        if filepath.suffix.lower() not in {".pdf", ".docx", ".doc"}:
            continue
        summary = LEGAL_SUMMARIES.get(filepath.stem, "Van ban phap luat ve phong, chong ma tuy.")
        converted_text = ""
        conversion_note = "Converted with fallback summary."

        if converter is not None:
            try:
                result = converter.convert(str(filepath))
                converted_text = (result.text_content or "").strip()
                if converted_text:
                    conversion_note = "Converted with Microsoft MarkItDown."
            except Exception as exc:
                conversion_note = f"MarkItDown conversion failed, fallback used: {exc}"

        content = (
            f"# {filepath.stem}\n\n"
            f"**Source file:** {filepath.name}\n"
            f"**Document type:** legal\n\n"
            f"**Conversion:** {conversion_note}\n\n"
            f"{converted_text or summary}\n\n"
            "Keywords: ma tuy, chat cam, phong chong ma tuy, hinh phat, cai nghien, "
            "tang tru trai phep, mua ban trai phep, tien chat.\n\n"
            f"File size: {filepath.stat().st_size} bytes.\n"
        )
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text(content, encoding="utf-8")
        outputs.append(output_path)
    return outputs


def convert_news_articles() -> list[Path]:
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for filepath in news_dir.iterdir():
        if filepath.suffix.lower() != ".json":
            continue
        data = json.loads(filepath.read_text(encoding="utf-8"))
        content = (
            f"# {data.get('title', 'Unknown')}\n\n"
            f"**Source:** {data.get('url', 'N/A')}\n"
            f"**Crawled:** {data.get('date_crawled', 'N/A')}\n"
            f"**Document type:** news\n\n"
            "---\n\n"
            f"{data.get('content_markdown', '')}"
        )
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text(content, encoding="utf-8")
        outputs.append(output_path)
    return outputs


def convert_all() -> list[Path]:
    outputs = []
    outputs.extend(convert_legal_docs())
    outputs.extend(convert_news_articles())
    print(f"Converted {len(outputs)} files to {OUTPUT_DIR}")
    return outputs


if __name__ == "__main__":
    convert_all()
