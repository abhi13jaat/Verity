import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.retrieval.dense_retriever import RetrievedChunk

log = logging.getLogger("verity.retrieval.sparse")


class SparseRetriever:
    async def retrieve(
        self, query: str, db: AsyncSession, top_k: int = 20, domain: str | None = None, user_id: str | None = None
    ) -> list[RetrievedChunk]:
        """Full-text search using PostgreSQL tsvector + GIN index."""
        log.info("[sparse] running FTS | top_k=%d | domain=%s | user=%s", top_k, domain, user_id)

        domain_filter = "AND d.domain = :domain" if domain else ""
        user_filter = "AND d.user_id = CAST(:user_id AS uuid)" if user_id else ""

        sql = text(f"""
            SELECT
                c.text,
                c.document_id::text,
                c.chunk_index,
                c.page_number,
                d.domain,
                ts_rank(c.search_vector, plainto_tsquery('english', :query)) AS score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.search_vector @@ plainto_tsquery('english', :query)
              {domain_filter}
              {user_filter}
            ORDER BY score DESC
            LIMIT :top_k
        """)

        params: dict = {"query": query, "top_k": top_k}
        if domain:
            params["domain"] = domain
        if user_id:
            params["user_id"] = str(user_id)

        result = await db.execute(sql, params)
        rows = result.fetchall()

        log.info("[sparse] found %d results", len(rows))
        return [
            RetrievedChunk(
                text=row.text,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
                score=float(row.score),
                domain=row.domain,
            )
            for row in rows
        ]
