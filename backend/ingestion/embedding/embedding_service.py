import logging

from fastembed import TextEmbedding

from backend.core.config import settings

log = logging.getLogger("verity.ingestion.embedding")


class EmbeddingService:
    def __init__(self):
        log.info("[embedding] loading model: %s", settings.embedding_model)
        self.model = TextEmbedding(model_name=settings.embedding_model)
        log.info("[embedding] model ready")

    def embed(self, texts: list[str]) -> list[list[float]]:
        log.info("[embedding] embedding %d texts...", len(texts))
        vectors = list(self.model.embed(texts))
        log.info("[embedding] done | count=%d", len(vectors))
        return [v.tolist() for v in vectors]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
