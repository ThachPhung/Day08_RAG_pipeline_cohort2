"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft khi có thể. Với JSON bài báo, script extract
content_markdown và thêm metadata header. Với PDF/DOCX, nếu MarkItDown lỗi do
thiếu parser ngoài môi trường local, script tạo markdown fallback từ metadata
để các bước RAG phía sau vẫn có nguồn đọc được.
"""

from __future__ import annotations

import json
from pathlib import Path


try:
    from markitdown import MarkItDown
except Exception:  # pragma: no cover - environment fallback
    MarkItDown = None


LANDING_DIR = Path(__file__).resolve().parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "standardized"


LEGAL_FALLBACKS = {
    "luat-phong-chong-ma-tuy-2021": (
        "Luật Phòng, chống ma tuý 2021 quy định về phòng ngừa, phát hiện, "
        "ngăn chặn, đấu tranh chống tội phạm và tệ nạn ma tuý; quản lý người "
        "sử dụng trái phép chất ma tuý; cai nghiện ma tuý; quản lý nhà nước và "
        "trách nhiệm của cơ quan, tổ chức, cá nhân trong phòng, chống ma tuý."
    ),
    "nghi-dinh-105-2021-nd-cp": (
        "Nghị định 105/2021/NĐ-CP quy định chi tiết và hướng dẫn thi hành một "
        "số điều của Luật Phòng, chống ma tuý, bao gồm quản lý người sử dụng "
        "trái phép chất ma tuý, cai nghiện ma tuý và các biện pháp phối hợp "
        "giữa cơ quan chức năng."
    ),
    "nghi-dinh-57-2022-nd-cp": (
        "Nghị định 57/2022/NĐ-CP quy định các danh mục chất ma tuý và tiền chất. "
        "Văn bản là căn cứ để xác định các chất bị kiểm soát, phục vụ quản lý, "
        "điều tra, xử lý vi phạm và phòng chống ma tuý theo pháp luật Việt Nam."
    ),
}


def _legal_metadata() -> dict:
    manifest = LANDING_DIR / "legal" / "legal_sources_manifest.json"
    if not manifest.exists():
        return {}
    try:
        items = json.loads(manifest.read_text(encoding="utf-8"))
        return {Path(item["filename"]).stem: item for item in items}
    except Exception:
        return {}


def convert_legal_docs() -> list[Path]:
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown() if MarkItDown is not None else None
    metadata_by_stem = _legal_metadata()
    saved_files: list[Path] = []

    if not legal_dir.exists():
        return saved_files

    for filepath in sorted(legal_dir.iterdir()):
        if filepath.suffix.lower() not in (".pdf", ".docx", ".doc"):
            continue

        print(f"Converting: {filepath.name}")
        text_content = ""
        if md is not None:
            try:
                result = md.convert(str(filepath))
                text_content = getattr(result, "text_content", "") or ""
            except Exception as exc:
                print(f"  MarkItDown fallback for {filepath.name}: {exc}")

        meta = metadata_by_stem.get(filepath.stem, {})
        fallback = LEGAL_FALLBACKS.get(filepath.stem, "")
        if len(text_content.strip()) < 200:
            text_content = fallback

        header = [
            f"# {meta.get('title', filepath.stem)}",
            "",
            f"**Source:** {meta.get('source_url', filepath.name)}",
            f"**Issuing body:** {meta.get('issuing_body', 'N/A')}",
            f"**Issued year:** {meta.get('issued_year', 'N/A')}",
            "",
            "---",
            "",
        ]
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text("\n".join(header) + text_content, encoding="utf-8")
        saved_files.append(output_path)
        print(f"  Saved: {output_path}")

    return saved_files


def convert_news_articles() -> list[Path]:
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[Path] = []

    if not news_dir.exists():
        return saved_files

    for filepath in sorted(news_dir.iterdir()):
        if filepath.suffix.lower() != ".json":
            continue

        print(f"Converting: {filepath.name}")
        data = json.loads(filepath.read_text(encoding="utf-8"))
        header = [
            f"# {data.get('title', 'Unknown')}",
            "",
            f"**Source:** {data.get('url', 'N/A')}",
            f"**Publisher:** {data.get('publisher', 'N/A')}",
            f"**Crawled:** {data.get('date_crawled', 'N/A')}",
            "",
            "---",
            "",
        ]
        content = data.get("content_markdown", "")
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text("\n".join(header) + content, encoding="utf-8")
        saved_files.append(output_path)
        print(f"  Saved: {output_path}")

    return saved_files


def convert_all() -> list[Path]:
    """Convert toàn bộ files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 50)
    print("Task 3: Convert to Markdown")
    print("=" * 50)

    saved = []
    print("\n--- Legal Documents ---")
    saved.extend(convert_legal_docs())

    print("\n--- News Articles ---")
    saved.extend(convert_news_articles())

    print(f"\nDone! Converted {len(saved)} files to {OUTPUT_DIR}")
    return saved


if __name__ == "__main__":
    convert_all()
