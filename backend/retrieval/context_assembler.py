from backend.retrieval.dense_retriever import RetrievedChunk


class ContextAssembler:
    def assemble(self, chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks into a numbered context string for the LLM."""
        parts = []
        for i, chunk in enumerate(chunks, start=1):
            page_info = f" (page {chunk.page_number})" if chunk.page_number else ""
            parts.append(f"[{i}]{page_info}\n{chunk.text}")
        return "\n\n---\n\n".join(parts)
