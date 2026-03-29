from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.ingestion.chunking.base import BaseChunker, TextChunk
from backend.ingestion.parsers.base import ParsedPage


class RecursiveChunker(BaseChunker):
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )

    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        index = 0
        for page in pages:
            splits = self.splitter.split_text(page.text)
            for split in splits:
                if split.strip():
                    chunks.append(self._make_chunk(split.strip(), index, page.page_number))
                    index += 1
        return chunks
