from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.ingestion.chunking.base import BaseChunker, TextChunk
from backend.ingestion.parsers.base import ParsedPage


class HeadingChunker(BaseChunker):
    """Each ParsedPage from DOCXParser is already one heading section.
    Sections that exceed max_chunk_size are split further with recursive splitting."""

    def __init__(self, max_chunk_size: int = 800, chunk_overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        index = 0
        for page in pages:
            text = page.text.strip()
            if not text:
                continue
            if len(text) <= self.max_chunk_size:
                chunks.append(self._make_chunk(text, index, page.page_number))
                index += 1
            else:
                for split in self.splitter.split_text(text):
                    if split.strip():
                        chunks.append(self._make_chunk(split.strip(), index, page.page_number))
                        index += 1
        return chunks
