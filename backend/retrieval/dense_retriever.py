import logging
from dataclasses import dataclass

from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.core.config import settings
from backend.db.qdrant_client import client as qdrant_client
from backend.ingestion.embedding.embedding_service import EmbeddingService

log = logging.getLogger("verity.retrieval.dense")


@dataclass
class RetrievedChunk:
    text: str
    document_id: str
    chunk_index: int
    page_number: int | None
    score: float
    domain: str | None


class DenseRetriever:
    def __init__(self):
        self.embedder = EmbeddingService()

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None, user_id: str | None = None) -> list[RetrievedChunk]:
        """Embed the query and search Qdrant for the most similar chunks."""
        log.info("[dense] embedding query...")
        vector = self.embedder.embed_one(query)

        must = []
        if user_id:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        if domain:
            must.append(FieldCondition(key="domain", match=MatchValue(value=domain)))
        query_filter = Filter(must=must) if must else None

        log.info("[dense] searching Qdrant | top_k=%d | domain=%s | user=%s", top_k, domain, user_id)
        results = qdrant_client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        log.info("[dense] found %d results", len(results))
        return [
            RetrievedChunk(
                text=r.payload["text"],
                document_id=r.payload["document_id"],
                chunk_index=r.payload["chunk_index"],
                page_number=r.payload.get("page_number"),
                score=r.score,
                domain=r.payload.get("domain"),
            )
            for r in results
        ]
