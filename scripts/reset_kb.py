"""
Wipe the knowledge base and re-ingest all arXiv PDFs from data/arxiv_papers/.

Steps:
  1. Delete all rows from chunks + documents tables in Postgres
  2. Delete + recreate the Qdrant collection (clears all vectors)
  3. Re-ingest every PDF found in data/arxiv_papers/ using the clean pipeline

Usage:
    python -m scripts.reset_kb                        # re-ingest all PDFs (no domain tag)
    python -m scripts.reset_kb --domain ml            # tag everything as "ml"
    python -m scripts.reset_kb --skip-ingest          # wipe only, no re-ingest
"""

import argparse
import asyncio
import os

from sqlalchemy import text

from backend.core.config import settings
from backend.db.postgres import AsyncSessionLocal
from backend.db.qdrant_client import client as qdrant_client, init_collection
from backend.ingestion.pipeline import ingest_document

DOWNLOAD_DIR = "data/arxiv_papers"


async def wipe_postgres() -> int:
    """Delete all chunks and documents. Returns number of documents deleted."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("DELETE FROM chunks"))
        chunks_deleted = result.rowcount
        result = await db.execute(text("DELETE FROM documents"))
        docs_deleted = result.rowcount
        await db.commit()
    print(f"  [postgres] deleted {docs_deleted} documents, {chunks_deleted} chunks")
    return docs_deleted


def wipe_qdrant() -> None:
    """Drop and recreate the Qdrant collection."""
    collections = [c.name for c in qdrant_client.get_collections().collections]
    if settings.qdrant_collection in collections:
        qdrant_client.delete_collection(settings.qdrant_collection)
        print(f"  [qdrant] dropped collection '{settings.qdrant_collection}'")
    init_collection()
    print(f"  [qdrant] recreated collection '{settings.qdrant_collection}'")


async def reingest_all(domain: str | None) -> None:
    """Re-ingest every PDF in DOWNLOAD_DIR."""
    if not os.path.isdir(DOWNLOAD_DIR):
        print(f"  [ingest] directory not found: {DOWNLOAD_DIR} — nothing to ingest")
        return

    pdfs = sorted(
        os.path.join(DOWNLOAD_DIR, f)
        for f in os.listdir(DOWNLOAD_DIR)
        if f.lower().endswith(".pdf")
    )

    if not pdfs:
        print(f"  [ingest] no PDFs found in {DOWNLOAD_DIR}")
        return

    print(f"  [ingest] found {len(pdfs)} PDFs — starting ingestion...")

    async with AsyncSessionLocal() as db:
        for i, pdf_path in enumerate(pdfs, start=1):
            title = os.path.splitext(os.path.basename(pdf_path))[0].replace("_", " ")
            print(f"  [{i}/{len(pdfs)}] {title[:70]}")
            try:
                doc = await ingest_document(
                    source=pdf_path,
                    title=title,
                    db=db,
                    domain=domain,
                )
                print(f"           ok | id={doc.id} | status={doc.status}")
            except Exception as exc:
                # Reset the session so one bad PDF doesn't poison the rest.
                await db.rollback()
                print(f"           FAILED: {exc}")

    print(f"  [ingest] done — {len(pdfs)} PDFs processed")


async def main_async(skip_ingest: bool, domain: str | None) -> None:
    print("\n=== Verity — Knowledge Base Reset ===\n")

    print("[1/3] Wiping Postgres...")
    await wipe_postgres()

    print("[2/3] Wiping Qdrant...")
    wipe_qdrant()

    if skip_ingest:
        print("\n[3/3] Skipping re-ingest (--skip-ingest flag set)")
    else:
        print(f"[3/3] Re-ingesting PDFs from {DOWNLOAD_DIR}/...")
        await reingest_all(domain=domain)

    print("\nReset complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset Verity knowledge base and re-ingest")
    parser.add_argument("--domain", default=None, help="Domain tag to apply to all re-ingested docs")
    parser.add_argument("--skip-ingest", action="store_true", help="Wipe only — do not re-ingest")
    args = parser.parse_args()

    asyncio.run(main_async(skip_ingest=args.skip_ingest, domain=args.domain))


if __name__ == "__main__":
    main()
