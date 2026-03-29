from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM — OpenRouter
    openrouter_api_key: str = Field(description="OpenRouter API key")
    llm_model: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free",
        description="OpenRouter model ID — use :free suffix for free models"
    )
    fast_llm_model: str = Field(
        default="google/gemma-3-4b-it:free",
        description="Smaller/faster model for domain check, HyDE — set FAST_LLM_MODEL in .env"
    )
    llm_provider: str | None = Field(
        default=None,
        description="OpenRouter provider preference e.g. 'Fireworks', 'Together', 'DeepInfra'. None = OpenRouter auto-selects."
    )

    # Databases
    postgres_url: str = Field(description="Async PostgreSQL connection string")
    qdrant_url: str = Field(description="Qdrant vector DB URL")
    qdrant_collection: str = Field(
        default="verity_chunks",
        description="Qdrant collection name for storing chunk vectors"
    )
    qdrant_api_key: str | None = Field(
        default=None,
        description="Qdrant Cloud API key (leave empty for local Qdrant)"
    )
    redis_url: str = Field(description="Redis connection URL")

    # Embedding
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Local sentence-transformers model — no API key required"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Output dimension of the embedding model — must match Qdrant collection size"
    )

    # Ingestion — LLM-heavy steps, OFF by default for fast ingestion
    enable_entity_extraction: bool = Field(
        default=False,
        description="Per-chunk LLM entity extraction for graph retrieval (many LLM calls — slow)"
    )
    enable_image_description: bool = Field(
        default=False,
        description="Vision-LLM descriptions for PDF figures (slow; needs vision-model credit)"
    )

    # Retrieval — cross-encoder reranking (ONNX via fastembed, torch-free)
    enable_reranker: bool = Field(
        default=True,
        description="Rerank RRF-fused candidates with a cross-encoder before final top-k"
    )
    reranker_model: str = Field(
        default="Xenova/ms-marco-MiniLM-L-6-v2",
        description="fastembed cross-encoder reranker model"
    )
    rerank_candidates: int = Field(
        default=30,
        description="How many fused candidates to rerank before taking top_k"
    )
    web_fallback_threshold: float = Field(
        default=0.6,
        description="If best dense cosine score is below this, treat as KB miss and fall back to web "
                    "search. bge-small scores any English text ~0.45-0.55, so a low bar wrongly keeps "
                    "off-topic queries in the KB and never triggers web search. Tune per embedding model."
    )

    # Langfuse (optional — leave empty to disable tracing)
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key for LLM tracing")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret key")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", description="Langfuse host URL")

    # Web Search (optional — Tavily for Adaptive KB)
    tavily_api_key: str | None = Field(default=None, description="Tavily API key for web search fallback")

    # App
    app_env: str = Field(
        default="development",
        description="Runtime environment: development | production"
    )
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated allowed CORS origins (frontend URLs)"
    )

    # Auth (JWT) — required; generate with: openssl rand -hex 32
    jwt_secret_key: str = Field(description="Secret for signing JWT access tokens")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(
        default=10080, description="Access token lifetime in minutes (default 7 days)"
    )


settings = Settings()
