from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.ingestion.parsers.base import ParsedPage


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page_number: int | None
    word_count: int


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, pages: list[ParsedPage]) -> list[TextChunk]:
        """Split parsed pages into smaller chunks ready for embedding."""
        ...

    def _make_chunk(self, text: str, index: int, page_number: int | None) -> TextChunk:
        return TextChunk(
            text=text,
            chunk_index=index,
            page_number=page_number,
            word_count=len(text.split()),
        )
