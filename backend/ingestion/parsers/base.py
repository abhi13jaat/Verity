from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParsedPage:
    text: str
    page_number: int | None


class BaseParser(ABC):
    @abstractmethod
    def parse(self, source: str) -> list[ParsedPage]:
        """Parse a document source (file path or URL) and return a list of pages."""
        ...
