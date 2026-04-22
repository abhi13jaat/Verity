"""
Seed the knowledge base with a sample document to verify the ingestion pipeline end-to-end.
Run: python -m scripts.seed_kb
"""

import asyncio
import os

from backend.db.postgres import AsyncSessionLocal
from backend.db.qdrant_client import init_collection
from backend.ingestion.pipeline import ingest_document

SAMPLE_PATH = "scripts/sample_rag.txt"

SAMPLE_TEXT = """
Retrieval-Augmented Generation (RAG) is a technique that combines information retrieval
with large language model generation to produce accurate, grounded answers.

When a user asks a question, the RAG system first embeds the query into a vector and
searches a vector database for the most semantically similar document chunks. These
retrieved chunks are then injected into the LLM prompt as context, allowing the model
to generate an answer that is grounded in real documents rather than relying solely
on its training data.

Dense retrieval uses vector embeddings to find semantically similar documents. Each
chunk is converted into a high-dimensional vector, and approximate nearest-neighbour
algorithms such as HNSW (Hierarchical Navigable Small World) are used to find the
closest vectors at query time.

Hybrid retrieval combines dense (vector) search with sparse (keyword) search such as
BM25 or PostgreSQL full-text search. The results are fused using Reciprocal Rank
Fusion (RRF), which balances exact keyword matches with semantic similarity.

Chunking strategies determine how documents are split before embedding. Recursive
character splitting is a good default for plain text and PDFs. Markdown-aware splitting
respects heading boundaries in Markdown files. Semantic chunking uses embeddings to
detect topic shifts and create more coherent chunks.
""".strip()


async def main() -> None:
    os.makedirs("scripts", exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        f.write(SAMPLE_TEXT)

    init_collection()

    async with AsyncSessionLocal() as db:
        doc = await ingest_document(
            source=SAMPLE_PATH,
            title="RAG Fundamentals",
            db=db,
            domain="ml",
        )

    print(f"Ingested | id={doc.id} | title={doc.title!r} | status={doc.status}")


if __name__ == "__main__":
    asyncio.run(main())
