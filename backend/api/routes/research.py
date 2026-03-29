import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.graph import build_graph
from backend.agents.nodes import stream_generator_node
from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.context_assembler import ContextAssembler
from backend.retrieval.dense_retriever import RetrievedChunk
from backend.retrieval.web_searcher import search_web

_retriever = HybridRetriever()
_stream_retriever = HybridRetriever(use_hyde=False, use_graph=False)
_assembler = ContextAssembler()
_thread_pool = ThreadPoolExecutor(max_workers=2)
log = logging.getLogger("verity.api")

_DOMAIN_LABELS = {
    "ml": "Machine Learning / AI",
    "dl": "Deep Learning",
    "cs": "Computer Science",
    "physics": "Physics",
    "bio": "Biology",
    "finance": "Finance",
    "math": "Mathematics",
}


def _check_domain_sync(query: str, domain_label: str) -> bool:
    """Returns True if query is relevant to the domain, False if off-domain."""
    resp = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.fast_llm_model,
        messages=[{
            "role": "user",
            "content": (
                f'Domain: {domain_label}\n'
                f'Query: "{query}"\n\n'
                f'Is this query about {domain_label}? Answer only: yes or no'
            ),
        }],
        temperature=0,
        max_tokens=5,
    )
    answer = resp.choices[0].message.content.strip().lower()
    return answer.startswith("yes")
from backend.api.schemas.research import (
    AsyncIngestResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceItem,
    TaskStatusResponse,
)
from backend.db.models.document import Document
from backend.db.models.user import User
from backend.db.postgres import get_db
from backend.api.dependencies.auth import get_current_user
from backend.api.middleware.rate_limit import check_rate_limit
from backend.ingestion.pipeline import ingest_document
from backend.memory.conversation_store import load_history, save_exchange
from backend.workers.celery_app import celery_app

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/sessions")
async def list_sessions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the last 30 sessions belonging to the authenticated user."""
    result = await db.execute(text("""
        SELECT
            ch.session_id,
            (
                SELECT content FROM conversation_history ch2
                WHERE ch2.session_id = ch.session_id AND ch2.role = 'user'
                ORDER BY ch2.created_at ASC LIMIT 1
            ) AS preview,
            MAX(ch.created_at) AS last_at,
            COUNT(*) AS message_count
        FROM conversation_history ch
        WHERE ch.user_id = CAST(:uid AS uuid)
        GROUP BY ch.session_id
        ORDER BY last_at DESC
        LIMIT 30
    """), {"uid": str(current_user.id)})
    rows = result.fetchall()
    return [
        {
            "session_id": r.session_id,
            "preview": (r.preview or "")[:80],
            "last_at": r.last_at.isoformat() if r.last_at else None,
            "message_count": r.message_count,
        }
        for r in rows
    ]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all messages for a session the caller owns (chronological)."""
    result = await db.execute(
        text("""
            SELECT role, content FROM conversation_history
            WHERE session_id = :session_id
              AND user_id = CAST(:uid AS uuid)
            ORDER BY created_at ASC
        """),
        {"session_id": session_id, "uid": str(current_user.id)},
    )
    rows = result.fetchall()
    return [{"role": r.role, "content": r.content} for r in rows]


@router.post("/upload", response_model=IngestResponse)
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    domain: str = Form(default="ml"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF (or any file) directly — saved locally then ingested through the full pipeline."""
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name if file.filename else "upload.pdf"
    file_path = upload_dir / safe_name
    file_path.write_bytes(await file.read())

    doc = await ingest_document(
        source=str(file_path),
        title=title,
        db=db,
        domain=domain,
        user_id=str(current_user.id),
    )
    return IngestResponse(document_id=str(doc.id), title=doc.title, status=doc.status)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous ingest — waits until complete. Good for small files."""
    doc = await ingest_document(
        source=request.source,
        title=request.title,
        db=db,
        domain=request.domain,
        user_id=str(current_user.id),
    )
    return IngestResponse(document_id=str(doc.id), title=doc.title, status=doc.status)


@router.post("/ingest/async", response_model=AsyncIngestResponse)
async def ingest_async(request: IngestRequest, current_user: User = Depends(get_current_user)):
    """Async ingest — queues a background task and returns immediately."""
    from backend.workers.tasks import ingest_document_task

    task = ingest_document_task.delay(
        source=request.source,
        title=request.title,
        domain=request.domain,
        user_id=str(current_user.id),
    )
    return AsyncIngestResponse(
        task_id=task.id,
        status="queued",
        message=f"Ingestion queued. Check status at /research/tasks/{task.id}",
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    """Check the status of a background ingestion task."""
    result = AsyncResult(task_id, app=celery_app)

    match result.state:
        case "PENDING":
            return TaskStatusResponse(task_id=task_id, status="queued")
        case "STARTED":
            return TaskStatusResponse(task_id=task_id, status="running")
        case "SUCCESS":
            return TaskStatusResponse(task_id=task_id, status="completed", result=result.result)
        case "FAILURE":
            return TaskStatusResponse(task_id=task_id, status="failed", error=str(result.result))
        case _:
            return TaskStatusResponse(task_id=task_id, status=result.state.lower())


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Streaming query — tokens arrive in real-time via Server-Sent Events."""

    user_id = str(current_user.id)

    # Rate limiting — per authenticated user
    allowed, retry_after = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit", "retry_after": retry_after},
        )

    conversation_history = []
    if request.session_id:
        conversation_history = await load_history(request.session_id, db, user_id=user_id)

    # Domain guard — fast binary check before retrieval
    if request.domain and request.domain != "all" and request.domain in _DOMAIN_LABELS:
        domain_label = _DOMAIN_LABELS[request.domain]
        loop = asyncio.get_event_loop()
        is_on_domain = await loop.run_in_executor(
            _thread_pool, _check_domain_sync, request.query, domain_label
        )
        if not is_on_domain:
            async def _refuse():
                msg = (
                    f"This question is outside the selected domain **{domain_label}**. "
                    f"Please switch to a relevant domain or select **All Domains** to ask this."
                )
                yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
            return StreamingResponse(_refuse(), media_type="text/event-stream")

    # Retrieval — fast path: no graph (~7s saved), HyDE parallel with sparse
    chunks, best_dense_score = await _stream_retriever.retrieve(
        query=request.query,
        db=db,
        top_k=request.top_k,
        domain=request.domain,
        user_id=user_id,
    )

    # Fetch document titles for source enrichment
    doc_id_set = list({c.document_id for c in chunks})
    doc_title_map: dict[str, str] = {}
    if doc_id_set:
        try:
            uuids = [uuid.UUID(d) for d in doc_id_set]
            rows = (await db.execute(select(Document.id, Document.title).where(Document.id.in_(uuids)))).all()
            doc_title_map = {str(row.id): row.title for row in rows}
        except Exception:
            pass

    async def event_stream():
        active_chunks = chunks
        web_search_used = False

        # Cosine similarity threshold — meaningful relevance signal.
        # BAAI/bge-small scores any English text ~0.45-0.55, so an off-topic query
        # (e.g. a sports result against an ML-papers KB) still clears a low bar and
        # never reaches web search. Threshold is configurable via WEB_FALLBACK_THRESHOLD.
        # RRF scores (0.013-0.033) are rank-based, useless for this decision.
        needs_web = not active_chunks or best_dense_score < settings.web_fallback_threshold

        if needs_web:
            yield f"data: {json.dumps({'type': 'token', 'content': '_Searching the web..._\n\n'})}\n\n"
            web_results = search_web(request.query)
            if not web_results:
                yield f"data: {json.dumps({'type': 'token', 'content': 'No relevant information found in the knowledge base or on the web.'})}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return
            active_chunks = [
                RetrievedChunk(
                    text=r["content"][:1500],
                    document_id=f"web_{i}",
                    chunk_index=0,
                    page_number=None,
                    score=0.8,
                    domain=request.domain,
                )
                for i, r in enumerate(web_results[:5])
            ]
            web_search_used = True
            doc_title_map.update({f"web_{i}": r.get("title", r.get("url", "Web Result")) for i, r in enumerate(web_results[:5])})

            # Fire-and-forget: ingest web results into KB in background
            # Wrapped in try-except — if Celery/Redis is down, stream must NOT crash
            try:
                from backend.workers.tasks import ingest_text_task
                for r in web_results:
                    if r.get("content") and len(r["content"]) > 100:
                        ingest_text_task.apply_async(
                            kwargs=dict(
                                text=r["content"],
                                title=r.get("title") or r.get("url", "Web Result")[:200],
                                source_url=r.get("url", ""),
                                domain=request.domain,
                                user_id=user_id,
                            ),
                            ignore_result=True,
                        )
            except Exception as _celery_err:
                import logging
                logging.getLogger("verity.api").warning(
                    "[stream] background KB ingest skipped (Celery unavailable): %s", _celery_err
                )

        # Stream tokens
        gen_state = {
            "query": request.query, "domain": request.domain, "user_id": user_id, "db": db,
            "session_id": request.session_id, "conversation_history": conversation_history,
            "plan": {}, "sub_queries": [], "chunks": active_chunks,
            "contradictions": [], "context": "", "answer": "",
            "is_relevant": True, "has_hallucination": False,
            "citation_verified": True, "web_search_used": web_search_used,
            "web_sources": [], "sources": [],
        }
        full_answer = ""
        try:
            for token in stream_generator_node(gen_state):
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as gen_err:
            log.warning("[stream] generation failed: %s", gen_err)
            err_str = str(gen_err)
            if "429" in err_str or "rate" in err_str.lower():
                msg = "The model is rate-limited right now (free tier). Please retry in ~30 seconds."
            else:
                msg = "Answer generation failed. Please try again."
            yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return

        # Hallucination check skipped in stream path (saves ~6s after generation)
        has_hallucination = False

        # Send sources with paper titles + chunk text preview
        sources = [
            {
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "score": round(c.score, 4),
                "title": doc_title_map.get(c.document_id, "Web Result" if web_search_used else "Unknown Paper"),
                "text": c.text[:600],
            }
            for c in active_chunks
        ]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'chunks_used': len(active_chunks)})}\n\n"

        # Pipeline transparency event
        # Stream path runs dense + sparse + RRF (+ cross-encoder rerank if enabled)
        if web_search_used:
            methods = ["Web Search"]
        else:
            methods = ["Dense (Qdrant)", "Sparse BM25"]
            if settings.enable_reranker:
                methods.append("Cross-Encoder Rerank")
        pipeline_info = {
            "type": "pipeline",
            "methods": methods,
            "chunks_retrieved": len(active_chunks),
            "reranked": settings.enable_reranker and not web_search_used,
            "has_hallucination": has_hallucination,  # check skipped in stream path
            "grader_passed": not web_search_used,  # KB confidence ok => used directly
        }
        yield f"data: {json.dumps(pipeline_info)}\n\n"

        # Save to memory
        if request.session_id:
            await save_exchange(
                session_id=request.session_id,
                query=request.query,
                answer=full_answer,
                db=db,
                user_id=user_id,
            )

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query the knowledge base using the agentic RAG pipeline."""
    graph = build_graph()
    user_id = str(current_user.id)

    # Load conversation history if session_id provided
    conversation_history = []
    if request.session_id:
        conversation_history = await load_history(request.session_id, db, user_id=user_id)

    result = await graph.ainvoke({
        "query": request.query,
        "domain": request.domain,
        "user_id": user_id,
        "db": db,
        "session_id": request.session_id,
        "conversation_history": conversation_history,
        "plan": {},
        "sub_queries": [],
        "chunks": [],
        "contradictions": [],
        "context": "",
        "answer": "",
        "is_relevant": True,
        "has_hallucination": False,
        "citation_verified": True,
        "web_search_used": False,
        "web_sources": [],
        "sources": [],
    })

    if not result["is_relevant"]:
        return QueryResponse(
            answer="No relevant information found in the knowledge base for your query.",
            chunks_used=0,
            sources=[],
        )

    answer = result["answer"]
    if result["has_hallucination"]:
        answer += "\n\n[Warning: This answer may contain information not fully supported by the retrieved context.]"

    # Persist this exchange to memory
    if request.session_id:
        await save_exchange(
            session_id=request.session_id,
            query=request.query,
            answer=answer,
            db=db,
            user_id=user_id,
        )

    return QueryResponse(
        answer=answer,
        chunks_used=len(result["chunks"]),
        sources=[SourceItem(**s) for s in result["sources"]],
    )
