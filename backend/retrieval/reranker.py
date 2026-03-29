"""Cross-encoder reranking — ONNX via fastembed (no torch).

RRF fusion is rank-based and cheap but blind to query-document semantics. A
cross-encoder scores each (query, chunk) pair jointly for relevance, giving a
much better final ordering. Applied to the top RRF candidates, then truncated
to top_k.
"""

import logging

from backend.core.config import settings
from backend.retrieval.dense_retriever import RetrievedChunk

log = logging.getLogger("verity.retrieval.rerank")

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        log.info("[rerank] loading model: %s", settings.reranker_model)
        _model = TextCrossEncoder(model_name=settings.reranker_model)
        log.info("[rerank] model ready")
    return _model


def rerank(query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    """Reorder chunks by cross-encoder relevance and return the top_k.

    Degrades gracefully: if the reranker is unavailable, returns the input order
    truncated to top_k (the RRF ranking).
    """
    if not chunks:
        return chunks
    try:
        scores = list(_get_model().rerank(query, [c.text for c in chunks]))
    except Exception as exc:
        log.warning("[rerank] unavailable, keeping fused order: %s", exc)
        return chunks[:top_k]

    for chunk, score in zip(chunks, scores):
        chunk.score = round(float(score), 4)
    ranked = sorted(chunks, key=lambda c: c.score, reverse=True)
    log.info("[rerank] reranked %d candidates -> top %d", len(chunks), top_k)
    return ranked[:top_k]
