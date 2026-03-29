import hashlib
import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client.models import PointStruct

from backend.core.config import settings
from backend.db.models.document import Document
from backend.db.models.chunk import Chunk
from backend.db.qdrant_client import client as qdrant_client
from backend.ingestion.parsers.pdf_parser import PDFParser
from backend.ingestion.parsers.docx_parser import DOCXParser
from backend.ingestion.parsers.txt_parser import TXTParser
from backend.ingestion.parsers.web_parser import WebParser
from backend.ingestion.parsers.base import BaseParser
from backend.ingestion.chunking.factory import get_chunker
from backend.ingestion.embedding.embedding_service import EmbeddingService
from backend.ingestion.cleaning.text_cleaner import clean_page_text, is_clean_chunk
from backend.ingestion.graph.entity_extractor import extract_entities
from sqlalchemy import select

log = logging.getLogger("verity.ingestion.pipeline")


def _detect_type(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return "web"
    ext = os.path.splitext(source)[1].lower()
    match ext:
        case ".pdf":  return "pdf"
        case ".docx": return "docx"
        case ".md":   return "md"
        case _:       return "txt"


def _get_parser(doc_type: str) -> BaseParser:
    match doc_type:
        case "pdf":  return PDFParser(extract_images=settings.enable_image_description)
        case "docx": return DOCXParser()
        case "web":  return WebParser()
        case _:      return TXTParser()


def _compute_hash(source: str) -> str | None:
    """SHA-256 hash of a local file. Returns None for URLs."""
    if source.startswith("http://") or source.startswith("https://"):
        return None
    try:
        h = hashlib.sha256()
        with open(source, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


async def ingest_document(
    source: str,
    title: str,
    db: AsyncSession,
    domain: str | None = None,
    user_id: str | None = None,
) -> Document:
    """Full ingestion pipeline: parse → chunk → embed → store in Qdrant + Postgres."""

    doc_type = _detect_type(source)
    log.info("[pipeline] starting | title=%r | type=%s | domain=%s", title, doc_type, domain)

    uid = uuid.UUID(user_id) if user_id else None

    # Hash deduplication — scoped per user (same user + same file → skip)
    file_hash = _compute_hash(source)
    if file_hash:
        existing = await db.scalar(
            select(Document).where(Document.file_hash == file_hash, Document.user_id == uid)
        )
        if existing:
            log.info("[pipeline] duplicate detected (hash=%s) — skipping | id=%s", file_hash[:12], existing.id)
            return existing

    parser = _get_parser(doc_type)
    chunker = get_chunker(doc_type)
    embedder = EmbeddingService()

    # Step 1: Parse
    log.info("[pipeline] step 1/7 — parsing...")
    pages = parser.parse(source)
    log.info("[pipeline] parsed %d pages", len(pages))

    # Step 2: Clean pages (remove noise before chunking)
    log.info("[pipeline] step 2/7 — cleaning %d pages...", len(pages))
    for page in pages:
        page.text = clean_page_text(page.text)
    pages = [p for p in pages if p.text.strip()]
    log.info("[pipeline] %d pages remain after cleaning", len(pages))

    # Step 3: Chunk
    log.info("[pipeline] step 3/7 — chunking...")
    text_chunks = chunker.chunk(pages)
    raw_count = len(text_chunks)

    # Step 4: Filter low-quality chunks
    log.info("[pipeline] step 4/7 — filtering chunks...")
    text_chunks = [c for c in text_chunks if is_clean_chunk(c.text)]
    log.info("[pipeline] kept %d/%d chunks after filter", len(text_chunks), raw_count)

    # Step 5: Embed
    log.info("[pipeline] step 5/7 — embedding %d chunks...", len(text_chunks))
    vectors = embedder.embed([c.text for c in text_chunks])
    log.info("[pipeline] embedded %d vectors (dim=%d)", len(vectors), len(vectors[0]) if vectors else 0)

    # Step 6: Save Document row
    log.info("[pipeline] step 6/7 — saving to Postgres...")
    doc = Document(title=title, source_path=source, domain=domain, status="processing", file_hash=file_hash, user_id=uid)
    db.add(doc)
    await db.flush()
    log.info("[pipeline] document saved | id=%s", doc.id)

    # Step 7: Build Qdrant points and Postgres chunk rows
    qdrant_points: list[PointStruct] = []
    db_chunks: list[Chunk] = []

    for chunk, vector in zip(text_chunks, vectors):
        qdrant_id = str(uuid.uuid4())
        entities = extract_entities(chunk.text) if settings.enable_entity_extraction else []

        qdrant_points.append(PointStruct(
            id=qdrant_id,
            vector=vector,
            payload={
                "document_id": str(doc.id),
                "user_id": user_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "text": chunk.text,
                "domain": domain,
                "entities": entities,
                "chunk_type": "base",
            },
        ))

        db_chunks.append(Chunk(
            document_id=doc.id,
            text=chunk.text,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            word_count=chunk.word_count,
            qdrant_id=qdrant_id,
        ))

    # Step 7a: Upsert vectors into Qdrant
    log.info("[pipeline] step 7/7 — storing %d vectors in Qdrant...", len(qdrant_points))
    qdrant_client.upsert(
        collection_name=settings.qdrant_collection,
        points=qdrant_points,
    )

    # Step 7b: Bulk insert chunks
    log.info("[pipeline] storing %d chunks in Postgres...", len(db_chunks))
    db.add_all(db_chunks)
    doc.status = "completed"
    await db.commit()
    await db.refresh(doc)

    log.info("[pipeline] done | id=%s | chunks=%d | status=%s", doc.id, len(db_chunks), doc.status)
    return doc
