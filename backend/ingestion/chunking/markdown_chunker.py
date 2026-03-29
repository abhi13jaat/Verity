from langchain_text_splitters import MarkdownTextSplitter

from backend.ingestion.chunking.base import BaseChunker, TextChunk
from backend.ingestion.parsers.base import ParsedPage


class MarkdownChunker(BaseChunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        full_text = "\n\n".join(p.text for p in pages)
        splits = self.splitter.split_text(full_text)
        return [
            self._make_chunk(s.strip(), i, None)
            for i, s in enumerate(splits)
            if s.strip()
        ]
