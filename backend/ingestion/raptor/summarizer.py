import logging
import uuid

import numpy as np
from qdrant_client.models import PointStruct
from sklearn.cluster import KMeans

from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs
from backend.db.qdrant_client import client as qdrant_client
from backend.ingestion.embedding.embedding_service import EmbeddingService

log = logging.getLogger("verity.raptor")
_embedder = EmbeddingService()

_SYSTEM = (
    "You are a research summarizer. "
    "Synthesize the key ideas from the following passages into one concise paragraph (5-7 sentences). "
    "Focus on main concepts, methods, and findings. No bullet points."
)


def _fetch_base_chunks(domain: str | None = None) -> list[dict]:
    """Scroll Qdrant and return all non-summary chunk payloads + vectors."""
    all_points = []
    offset = None

    while True:
        batch, next_offset = qdrant_client.scroll(
            collection_name=settings.qdrant_collection,
            with_payload=True,
            with_vectors=True,
            limit=200,
            offset=offset,
        )
        all_points.extend(batch)
        if next_offset is None:
            break
        offset = next_offset

    chunks = [
        {
            "id": str(p.id),
            "text": p.payload["text"],
            "vector": p.vector,
            "domain": p.payload.get("domain"),
        }
        for p in all_points
        if p.vector is not None
        and p.payload.get("chunk_type") != "summary"
        and (domain is None or p.payload.get("domain") == domain)
    ]
    log.info("[raptor] fetched %d base chunks from Qdrant", len(chunks))
    return chunks


def _cluster(chunks: list[dict], n_clusters: int) -> list[list[dict]]:
    vectors = np.array([c["vector"] for c in chunks], dtype=np.float32)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(vectors)

    groups: list[list[dict]] = [[] for _ in range(n_clusters)]
    for chunk, label in zip(chunks, labels):
        groups[label].append(chunk)
    return groups


def _summarize_cluster(texts: list[str]) -> str:
    combined = "\n\n---\n\n".join(t[:500] for t in texts[:8])
    response = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": combined},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def build_raptor_summaries(domain: str | None = None) -> int:
    """Cluster all base chunks and upsert cluster summaries into Qdrant as level-1 nodes.

    Summary points carry chunk_type='summary' and level=1 in their payload so
    retrievers can distinguish them from raw chunks.
    Returns the number of summaries created.
    """
    chunks = _fetch_base_chunks(domain=domain)
    if len(chunks) < 4:
        log.warning("[raptor] only %d chunks — need at least 4 to cluster", len(chunks))
        return 0

    n_clusters = max(2, min(len(chunks) // 10, 50))
    log.info("[raptor] clustering %d chunks into %d groups...", len(chunks), n_clusters)
    groups = _cluster(chunks, n_clusters)

    summary_points: list[PointStruct] = []
    for i, group in enumerate(groups):
        if not group:
            continue
        texts = [c["text"] for c in group]
        log.info("[raptor] summarizing cluster %d/%d (%d chunks)...", i + 1, n_clusters, len(texts))
        summary_text = _summarize_cluster(texts)
        summary_vector = _embedder.embed_one(summary_text)

        summary_points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=summary_vector,
            payload={
                "text": summary_text,
                "chunk_type": "summary",
                "level": 1,
                "domain": group[0].get("domain"),
                "source_chunk_count": len(texts),
                "document_id": "raptor_summary",
                "chunk_index": i,
                "page_number": None,
            },
        ))

    if summary_points:
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=summary_points,
        )
        log.info("[raptor] stored %d summary nodes in Qdrant", len(summary_points))

    return len(summary_points)
