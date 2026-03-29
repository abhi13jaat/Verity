import logging
import uuid
from collections import defaultdict, deque

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.conversation import ConversationHistory

log = logging.getLogger("verity.memory")

# Short-term in-memory cache: session_id → last 10 messages
_cache: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))

MAX_HISTORY = 5  # Q&A pairs passed to the LLM


async def load_history(session_id: str, db: AsyncSession, user_id: str | None = None) -> list[dict]:
    """Load the last MAX_HISTORY exchanges from Postgres for a session."""
    user_filter = "AND user_id = CAST(:user_id AS uuid)" if user_id else ""
    params: dict = {"session_id": session_id, "limit": MAX_HISTORY * 2}
    if user_id:
        params["user_id"] = str(user_id)
    result = await db.execute(
        text(f"""
            SELECT role, content FROM conversation_history
            WHERE session_id = :session_id
              {user_filter}
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        params,
    )
    rows = result.fetchall()
    messages = [{"role": r.role, "content": r.content} for r in reversed(rows)]
    log.info("[memory] loaded %d messages for session=%s", len(messages), session_id)

    # Warm in-memory cache
    for m in messages:
        _cache[session_id].append(m)

    return messages


async def save_exchange(session_id: str, query: str, answer: str, db: AsyncSession, user_id: str | None = None) -> None:
    """Persist a Q&A pair to Postgres and update the in-memory cache."""
    uid = uuid.UUID(user_id) if user_id else None
    db.add(ConversationHistory(session_id=session_id, user_id=uid, role="user", content=query))
    db.add(ConversationHistory(session_id=session_id, user_id=uid, role="assistant", content=answer[:2000]))
    await db.commit()

    _cache[session_id].append({"role": "user", "content": query})
    _cache[session_id].append({"role": "assistant", "content": answer[:2000]})
    log.info("[memory] saved exchange for session=%s", session_id)


def get_cached_history(session_id: str) -> list[dict]:
    """Fast in-memory history lookup (no DB hit)."""
    return list(_cache[session_id])
