"""
Download papers from arXiv and ingest them into Verity.

Usage:
    python -m scripts.arxiv_ingest --query "RAG retrieval augmented generation" --max 5
    python -m scripts.arxiv_ingest --query "transformer attention mechanism" --max 3 --domain ml
"""

import argparse
import asyncio
import os

import arxiv
import httpx

from backend.db.postgres import AsyncSessionLocal
from backend.db.qdrant_client import init_collection
from backend.ingestion.pipeline import ingest_document

DOWNLOAD_DIR = "data/arxiv_papers"


def download_papers(query: str, max_results: int) -> list[dict]:
    """Search arXiv and download PDFs. Returns list of {path, title}."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    client = arxiv.Client(delay_seconds=5, num_retries=5)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    downloaded = []
    for paper in client.results(search):
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in paper.title)
        safe_title = safe_title[:80].strip()
        pdf_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}.pdf")

        if os.path.exists(pdf_path):
            print(f"  [skip] already downloaded: {paper.title}")
        else:
            print(f"  [download] {paper.title}")
            response = httpx.get(paper.pdf_url, follow_redirects=True, timeout=60)
            with open(pdf_path, "wb") as f:
                f.write(response.content)

        downloaded.append({"path": pdf_path, "title": paper.title})

    return downloaded


async def ingest_papers(papers: list[dict], domain: str | None) -> None:
    """Ingest all downloaded PDFs into Verity."""
    init_collection()

    async with AsyncSessionLocal() as db:
        for i, paper in enumerate(papers, start=1):
            print(f"  [{i}/{len(papers)}] ingesting: {paper['title']}")
            try:
                doc = await ingest_document(
                    source=paper["path"],
                    title=paper["title"],
                    db=db,
                    domain=domain,
                )
                print(f"           done | id={doc.id} | status={doc.status}")
            except Exception as e:
                # Reset the session so one bad paper doesn't poison the rest
                # (a failed flush leaves the transaction un-usable until rollback).
                await db.rollback()
                print(f"           failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv → Verity ingestion script")
    parser.add_argument("--query", required=True, help="arXiv search query")
    parser.add_argument("--max", type=int, default=5, help="Max number of papers to download")
    parser.add_argument("--domain", default=None, help="Domain tag for filtering (e.g. ml, physics)")
    args = parser.parse_args()

    print(f"\nSearching arXiv: '{args.query}' (max {args.max} papers)\n")
    papers = download_papers(query=args.query, max_results=args.max)

    print(f"\nIngesting {len(papers)} papers into Verity...\n")
    asyncio.run(ingest_papers(papers=papers, domain=args.domain))

    print(f"\nDone. {len(papers)} papers ingested.")
    print(f"PDFs saved in: {DOWNLOAD_DIR}/")


if __name__ == "__main__":
    main()
