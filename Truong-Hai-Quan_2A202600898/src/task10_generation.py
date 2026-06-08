"""
Task 10 — Generation Có Citation.

Luồng: retrieve (Task 9) → reorder chống "lost in the middle" → format context
kèm nhãn nguồn → gọi LLM với SYSTEM_PROMPT bắt buộc trích dẫn → trả answer.

Tham số sinh (giải thích):
    - TEMPERATURE = 0.3: RAG cần factual, ít sáng tạo → nhiệt độ thấp cho ổn định.
    - TOP_P = 0.9: nucleus sampling vừa phải, tránh token rác mà vẫn tự nhiên.
    - TOP_K (số chunk) = 5: đủ evidence nhưng không quá dài gây loãng ngữ cảnh.
"""

import os

from dotenv import load_dotenv

from src.rag_common import _force_utf8_stdout
from src.task9_retrieval_pipeline import retrieve

load_dotenv()
_force_utf8_stdout()

# =============================================================================
# CONFIGURATION
# =============================================================================
TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
GEN_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Bạn là trợ lý pháp lý trả lời bằng tiếng Việt, chỉ dựa trên CONTEXT được cung cấp.
Với MỌI khẳng định/sự kiện, chèn ngay một trích dẫn trong ngoặc vuông trỏ tới nguồn cụ thể,
ví dụ: [Luật Phòng chống ma tuý 2021, Điều 3] hoặc [VnExpress, 2024].

Nếu thông tin KHÔNG có rõ ràng trong context, hãy trả lời đúng câu:
'Tôi không thể xác minh thông tin này từ nguồn hiện có.' — tuyệt đối không bịa.

Quy tắc:
- Chỉ dùng thông tin trong context.
- Mỗi ý factual PHẢI có citation.
- Nếu context không đủ, nói rõ.
- Trình bày mạch lạc theo đoạn."""


# =============================================================================
# DOCUMENT REORDERING (chống lost in the middle)
# =============================================================================
def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp để chunk quan trọng nằm ở ĐẦU và CUỐI, kém quan trọng dồn vào GIỮA
    (LLM chú ý 2 biên tốt hơn phần giữa — Liu et al. 2023).

    Vào (theo score giảm dần): [d0, d1, d2, d3, d4]
    Ra:                        [d0, d2, d4, d3, d1]   (d0 tốt nhất vẫn đứng đầu)
    """
    if len(chunks) <= 2:
        return list(chunks)

    ordered = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    left, right = [], []
    for i, c in enumerate(ordered):
        (left if i % 2 == 0 else right).append(c)
    return left + right[::-1]


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================
def format_context(chunks: list[dict]) -> str:
    """Render chunks thành context có nhãn nguồn để LLM cite được."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {}) or {}
        source = meta.get("source", f"Nguồn {i}")
        doc_type = meta.get("doc_type") or meta.get("type", "unknown")
        parts.append(
            f"[Tài liệu {i} | Nguồn: {source} | Loại: {doc_type}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


# =============================================================================
# GENERATION
# =============================================================================
def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    RAG generation end-to-end có citation.

    Returns:
        {'answer': str, 'sources': list[dict], 'retrieval_source': str}
    """
    chunks = retrieve(query, top_k=top_k)

    if not chunks:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": [],
            "retrieval_source": "none",
        }

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)
    user_message = f"CONTEXT:\n{context}\n\n---\n\nCÂU HỎI: {query}"

    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
    )
    answer = response.choices[0].message.content or ""

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid"),
    }


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]
    for q in test_queries:
        print(f"\n{'='*70}\nQ: {q}\n{'='*70}")
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
