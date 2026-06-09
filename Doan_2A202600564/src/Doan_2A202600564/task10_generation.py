"""
Task 10 — Generation Có Citation.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from src.task9_retrieval_pipeline import retrieve

# top_k=5: đủ evidence, tránh context quá dài gây lost in the middle
TOP_K = 5
# top_p=0.9: nucleus sampling cân bằng đa dạng và ổn định
TOP_P = 0.9
# temperature=0.3: factual, ít hallucination
TEMPERATURE = 0.3

SYSTEM_PROMPT = """Answer the following question comprehensively in Vietnamese.
For every statement of fact or claim, immediately insert a citation in brackets
linking to the specific source (e.g., [Luật Phòng chống ma tuý 2021, Điều 3]
or [VnExpress, 2024]).

If the information is not explicitly stated in the provided context or knowledge
base, state 'Tôi không thể xác minh thông tin này từ nguồn hiện có' rather than
guessing.

Rules:
- Only use information from the provided context
- Every factual claim MUST have a citation
- If context is insufficient, say so clearly
- Structure your answer with clear paragraphs"""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Đặt chunk quan trọng nhất ở đầu và cuối prompt (lost in the middle).
  [0,1,2,3,4] → [0,2,4,3,1]
    """
    if len(chunks) <= 2:
        return chunks

    n = len(chunks)
    result: list[dict | None] = [None] * n
    left, right = 0, n - 1
    for i, chunk in enumerate(chunks):
        if i % 2 == 0:
            result[left] = chunk
            left += 1
        else:
            result[right] = chunk
            right -= 1
    return [c for c in result if c is not None]


def format_context(chunks: list[dict]) -> str:
    """Format chunks thành context string có nhãn nguồn."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", f"Source {i}")
        doc_type = metadata.get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


def _generate_from_context(query: str, context: str) -> str:
    """Gọi OpenAI nếu có API key, không thì trả lời extractive đơn giản."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and not api_key.startswith("sk-xxx"):
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return response.choices[0].message.content or ""

    if not context.strip():
        return "Tôi không thể xác minh thông tin này từ nguồn hiện có."

    first_source = "Nguồn hiện có"
    for line in context.splitlines():
        if line.startswith("[Document") and "Source:" in line:
            first_source = line.split("Source:")[-1].split("|")[0].strip()
            break

    snippet = context[:1200].replace("\n", " ").strip()
    return (
        f"Theo [{first_source}], {snippet[:500]}... "
        f"(Trả lời tóm tắt từ context — cần OPENAI_API_KEY để sinh câu trả lời đầy đủ.)"
    )


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """End-to-end RAG generation có citation."""
    chunks = retrieve(query, top_k=top_k)
    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)
    answer = _generate_from_context(query, context)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none",
    }


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]

    for q in test_queries:
        print(f"\n{'=' * 70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
