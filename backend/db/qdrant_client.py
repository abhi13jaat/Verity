from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams
from backend.core.config import settings


client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def init_collection():
    """Create the Qdrant collection on startup if it does not already exist."""
    existing = [c.name for c in client.get_collections().collections]

    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dimension,
                distance=Distance.COSINE,
            ),
        )
        print(f"Created collection: {settings.qdrant_collection}")
    else:
        print(f"Collection already exists: {settings.qdrant_collection}")

    # Payload indexes for fast filtering on every retrieval (idempotent).
    for field in ("user_id", "domain"):
        try:
            client.create_payload_index(
                collection_name=settings.qdrant_collection,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # index already exists
