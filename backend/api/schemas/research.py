from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source: str = Field(description="File path or URL to ingest")
    title: str = Field(description="Human-readable document title")
    domain: str | None = Field(default=None, description="Optional domain tag for filtering during retrieval")


class IngestResponse(BaseModel):
    document_id: str
    title: str
    status: str


class QueryRequest(BaseModel):
    query: str = Field(description="Research question to answer")
    top_k: int = Field(default=8, description="Number of chunks to retrieve from the vector store")
    domain: str | None = Field(default=None, description="Filter retrieval to a specific domain")
    session_id: str | None = Field(default=None, description="Session ID for conversation memory")


class SourceItem(BaseModel):
    document_id: str
    chunk_index: int
    page_number: int | None
    score: float
    title: str | None = None
    text: str | None = None


class QueryResponse(BaseModel):
    answer: str
    chunks_used: int
    sources: list[SourceItem]


class AsyncIngestResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None
