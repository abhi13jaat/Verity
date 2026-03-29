from typing import Any, TypedDict


class AgentState(TypedDict):
    query: str
    domain: str | None
    user_id: str | None           # owner — scopes retrieval/ingest to this user
    db: Any                       # AsyncSession — passed per request, not serialized
    session_id: str | None        # for memory system
    conversation_history: list    # list of {"role": ..., "content": ...}
    plan: dict                    # planner output — approach, complexity, notes
    sub_queries: list[str]        # decomposed sub-questions
    chunks: list
    contradictions: list[dict]    # detected contradictions between chunks
    context: str
    answer: str
    is_relevant: bool
    has_hallucination: bool
    citation_verified: bool       # whether citations were verified
    web_search_used: bool         # whether web search was triggered
    web_sources: list[dict]       # web search result metadata
    sources: list[dict]
