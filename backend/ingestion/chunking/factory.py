from backend.ingestion.chunking.base import BaseChunker
from backend.ingestion.chunking.recursive_chunker import RecursiveChunker
from backend.ingestion.chunking.heading_chunker import HeadingChunker
from backend.ingestion.chunking.markdown_chunker import MarkdownChunker
from backend.ingestion.chunking.semantic_chunker import SemanticChunker


def get_chunker(doc_type: str) -> BaseChunker:
    """Return the appropriate chunker for the given document type."""
    match doc_type:
        case "pdf" | "txt":
            return RecursiveChunker()
        case "docx":
            return HeadingChunker()
        case "md":
            return MarkdownChunker()
        case "web":
            return SemanticChunker()
        case _:
            return RecursiveChunker()
