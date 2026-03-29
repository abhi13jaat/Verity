from backend.ingestion.chunking.base import BaseChunker, TextChunk
from backend.ingestion.chunking.recursive_chunker import RecursiveChunker
from backend.ingestion.parsers.base import ParsedPage


class SemanticChunker(BaseChunker):
    """For web content — delegates to RecursiveChunker since fastembed-based
    semantic splitting is not available without sentence-transformers."""

    def __init__(self):
        self._inner = RecursiveChunker()

    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        return self._inner.chunk(pages)
