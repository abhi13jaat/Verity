import asyncio
import logging

from backend.workers.celery_app import celery_app

log = logging.getLogger("verity.workers.tasks")


@celery_app.task(name="ingest_document", bind=True)
def ingest_document_task(self, source: str, title: str, domain: str | None = None, user_id: str | None = None) -> dict:
    """Background task — parse, chunk, embed, and store a document."""
    log.info("[task] ingest_document started | title=%r | source=%s", title, source)

    async def _run() -> dict:
        from backend.db.postgres import AsyncSessionLocal
        from backend.db.qdrant_client import init_collection
        from backend.ingestion.pipeline import ingest_document

        init_collection()
        async with AsyncSessionLocal() as db:
            doc = await ingest_document(source=source, title=title, db=db, domain=domain, user_id=user_id)
            return {"document_id": str(doc.id), "title": doc.title, "status": doc.status}

    result = asyncio.run(_run())
    log.info("[task] ingest_document done | document_id=%s", result["document_id"])
    return result


@celery_app.task(name="ingest_text", bind=True)
def ingest_text_task(
    self,
    text: str,
    title: str,
    source_url: str = "",
    domain: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Background task — ingest raw text (e.g. from web search) into the KB."""
    log.info("[task] ingest_text started | title=%r", title)

    async def _run() -> dict:
        import tempfile, os
        from backend.db.postgres import AsyncSessionLocal
        from backend.db.qdrant_client import init_collection
        from backend.ingestion.pipeline import ingest_document

        init_collection()

        # Write text to a temp .txt file so the pipeline can handle it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(f"Source: {source_url}\n\n{text}")
            tmp_path = f.name

        try:
            async with AsyncSessionLocal() as db:
                doc = await ingest_document(source=tmp_path, title=title, db=db, domain=domain, user_id=user_id)
                return {"document_id": str(doc.id), "status": doc.status}
        finally:
            os.unlink(tmp_path)

    result = asyncio.run(_run())
    log.info("[task] ingest_text done | document_id=%s", result["document_id"])
    return result
