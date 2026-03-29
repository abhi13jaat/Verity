import json
import logging
import time
from collections.abc import Generator

log = logging.getLogger("verity.agent")

from backend.agents.state import AgentState
from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs
from backend.prompts.report import build_report_prompt
from backend.retrieval.context_assembler import ContextAssembler
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.retrieval.web_searcher import search_web

_retriever = HybridRetriever()
_assembler = ContextAssembler()

# Langfuse tracing — enabled only when keys are configured
_langfuse = None
if settings.langfuse_public_key and settings.langfuse_secret_key:
    from langfuse import Langfuse
    _langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    log.info("Langfuse tracing enabled")


def decomposer_node(state: AgentState) -> dict:
    """Break a complex query into 2-3 focused sub-questions.

    Simple queries pass through unchanged (sub_queries stays empty).
    Complex queries get decomposed so each sub-query can retrieve
    its own focused set of chunks.
    """
    query = state["query"]
    log.info("[decomposer] checking if query needs decomposition...")

    prompt = f"""You are a query decomposer for a research assistant.
Decide if this query is complex enough to split into sub-questions.

Query: {query}

Rules:
- If simple (single concept) → return {{"decompose": false, "sub_queries": []}}
- If complex (multiple concepts / comparison / multi-part) → return {{"decompose": true, "sub_queries": ["q1", "q2", "q3"]}}
- Max 3 sub-queries, each focused and standalone
- Return ONLY valid JSON"""

    try:
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        data = json.loads(response.choices[0].message.content)
        if data.get("decompose") and data.get("sub_queries"):
            sub_queries = data["sub_queries"][:3]
            log.info("[decomposer] decomposed into %d sub-queries: %s", len(sub_queries), sub_queries)
            return {"sub_queries": sub_queries}
    except (json.JSONDecodeError, Exception) as exc:
        log.debug("[decomposer] failed, passing through: %s", exc)

    log.info("[decomposer] query is simple — no decomposition")
    return {"sub_queries": []}


async def retriever_node(state: AgentState) -> dict:
    """Retrieve relevant chunks using hybrid retrieval.

    If sub_queries are present (from decomposer), runs retrieval for each
    sub-query and merges results before returning.
    """
    sub_queries = state.get("sub_queries") or []

    if sub_queries:
        log.info("[retriever] running retrieval for %d sub-queries...", len(sub_queries))
        seen_keys: set[str] = set()
        merged: list = []

        for sq in sub_queries:
            sq_chunks, _ = await _retriever.retrieve(
                sq, db=state["db"], top_k=5, domain=state["domain"], user_id=state.get("user_id")
            )
            for c in sq_chunks:
                key = f"{c.document_id}_{c.chunk_index}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    merged.append(c)

        merged = sorted(merged, key=lambda c: c.score, reverse=True)[:5]
        log.info("[retriever] merged %d unique chunks from sub-queries", len(merged))
        return {"chunks": merged}

    log.info("[retriever] running hybrid retrieval...")
    chunks, best_dense_score = await _retriever.retrieve(
        state["query"], db=state["db"], top_k=5, domain=state["domain"], user_id=state.get("user_id")
    )
    log.info("[retriever] found %d chunks | best_dense=%.3f", len(chunks), best_dense_score)
    return {"chunks": chunks}


def web_search_node(state: AgentState) -> dict:
    """Fetch web results when KB has no relevant content.

    Web results are used as context for the current query.
    Background ingestion into KB happens via Celery (fire-and-forget)
    so the next query on the same topic gets a direct KB hit.
    """
    log.info("[web_search] KB had no relevant chunks — searching web...")
    results = search_web(state["query"], max_results=5)

    if not results:
        log.info("[web_search] no web results found either")
        return {"chunks": [], "web_search_used": True, "web_sources": []}

    # Convert web results into fake chunk objects so generator can use them
    from backend.retrieval.dense_retriever import RetrievedChunk
    web_chunks = [
        RetrievedChunk(
            text=r["content"],
            document_id="web_search",
            chunk_index=i,
            page_number=None,
            score=0.7,
            domain=state.get("domain"),
        )
        for i, r in enumerate(results)
        if r.get("content", "").strip()
    ]

    web_sources = [{"title": r["title"], "url": r["url"]} for r in results]
    log.info("[web_search] using %d web results as context", len(web_chunks))

    # Fire-and-forget: ingest web content into KB in background
    _trigger_background_ingest(results, domain=state.get("domain"), user_id=state.get("user_id"))

    return {
        "chunks": web_chunks,
        "web_search_used": True,
        "web_sources": web_sources,
        "is_relevant": True,
    }


def _trigger_background_ingest(results: list[dict], domain: str | None, user_id: str | None = None) -> None:
    """Queue web content for KB ingestion via Celery."""
    try:
        from backend.workers.tasks import ingest_text_task
        for r in results:
            if r.get("content", "").strip():
                ingest_text_task.delay(
                    text=r["content"],
                    title=r.get("title", "Web Result"),
                    source_url=r.get("url", ""),
                    domain=domain,
                    user_id=user_id,
                )
        log.info("[web_search] queued %d results for background ingestion", len(results))
    except Exception as exc:
        log.warning("[web_search] background ingest queue failed: %s", exc)


def grader_node(state: AgentState) -> dict:
    """Ask the LLM whether the retrieved chunks are relevant to the query."""
    log.info("[grader] checking relevance of %d chunks...", len(state["chunks"]))
    if not state["chunks"]:
        log.info("[grader] no chunks — marking not relevant")
        return {"is_relevant": False}

    preview = "\n\n".join(c.text[:300] for c in state["chunks"][:3])

    prompt = f"""You are a relevance grader. Decide if the retrieved document chunks are useful for answering the query.

Query: {state["query"]}

Retrieved chunks:
{preview}

Reply with JSON only — no explanation:
{{"relevant": true}} or {{"relevant": false}}"""

    response = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    try:
        data = json.loads(response.choices[0].message.content)
        is_relevant = bool(data.get("relevant", True))
        log.info("[grader] decision: %s", "relevant" if is_relevant else "NOT relevant")
        return {"is_relevant": is_relevant}
    except (json.JSONDecodeError, AttributeError):
        log.info("[grader] parse failed — defaulting to relevant")
        return {"is_relevant": True}


def generator_node(state: AgentState) -> dict:
    """Assemble context and generate an answer using Groq."""
    log.info("[generator] generating answer from %d chunks...", len(state["chunks"]))
    context = _assembler.assemble(state["chunks"])
    prompt = build_report_prompt(
        context=context,
        question=state["query"],
        conversation_history=state.get("conversation_history"),
        domain=state.get("domain"),
    )

    trace = _langfuse.trace(name="rag-query", input={"query": state["query"]}) if _langfuse else None
    span = trace.span(name="generator", input={"chunks": len(state["chunks"])}) if trace else None

    response = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    answer = response.choices[0].message.content
    usage = response.usage

    if span:
        span.end(output={
            "answer_length": len(answer),
            "total_tokens": usage.total_tokens if usage else None,
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "completion_tokens": usage.completion_tokens if usage else None,
        })
    if trace:
        trace.update(output={"answer_preview": answer[:200]})

    sources = [
        {
            "document_id": c.document_id,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "score": round(c.score, 4),
        }
        for c in state["chunks"]
    ]

    log.info("[generator] answer generated (%d chars) | tokens=%s",
             len(answer), usage.total_tokens if usage else "?")
    return {"answer": answer, "context": context, "sources": sources}


def stream_generator_node(state: AgentState) -> Generator[str, None, dict]:
    """Streaming version of generator — yields tokens as they arrive from Groq.

    Yields raw token strings. The caller is responsible for collecting them
    into the final answer and updating state.
    """
    log.info("[generator:stream] starting for %d chunks...", len(state["chunks"]))
    context = _assembler.assemble(state["chunks"])
    prompt = build_report_prompt(
        context=context,
        question=state["query"],
        conversation_history=state.get("conversation_history"),
        domain=state.get("domain"),
    )

    # Retry the initial call — free OpenRouter models are often transiently
    # rate-limited (429); a retry may route to a less-congested provider.
    stream = None
    for attempt in range(3):
        try:
            stream = _llm.chat.completions.create(**provider_kwargs(),
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096,
                stream=True,
            )
            break
        except Exception as exc:
            if attempt < 2:
                log.warning("[generator:stream] LLM call failed (attempt %d/3), retrying: %s", attempt + 1, exc)
                time.sleep(2)
            else:
                raise

    for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token

    log.info("[generator:stream] stream complete")


def planner_node(state: AgentState) -> dict:
    """High-level planning — decide approach before retrieval starts.

    Outputs a plan dict and sets sub_queries if the query is complex.
    This replaces the need for a separate decomposer node.
    """
    query = state["query"]
    log.info("[planner] analyzing query...")

    prompt = f"""You are a research query planner. Analyze this query and return a JSON plan.

Query: {query}

Return JSON only:
{{
  "complexity": "simple" | "moderate" | "complex",
  "approach": "direct" | "multi_step" | "comparative",
  "sub_queries": [],
  "notes": "brief note on strategy"
}}

Rules for sub_queries:
- simple/direct → empty list []
- moderate → 2 sub-queries
- complex/comparative → 2-3 sub-queries, each standalone and focused"""

    try:
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=250,
        )
        plan = json.loads(response.choices[0].message.content)
        sub_queries = [q for q in plan.get("sub_queries", []) if q.strip()][:3]
        log.info("[planner] complexity=%s | approach=%s | sub_queries=%d",
                 plan.get("complexity"), plan.get("approach"), len(sub_queries))
        return {"plan": plan, "sub_queries": sub_queries}
    except Exception as exc:
        log.warning("[planner] failed, using defaults: %s", exc)
        return {"plan": {"complexity": "simple", "approach": "direct", "notes": "fallback"}, "sub_queries": []}


def contradiction_detector_node(state: AgentState) -> dict:
    """Detect contradictions between retrieved chunks before generation.

    If contradictions are found they are appended to the context so the
    generator can acknowledge them in the answer.
    """
    chunks = state["chunks"]
    log.info("[contradiction_detector] checking %d chunks for contradictions...", len(chunks))

    if len(chunks) < 2:
        return {"contradictions": []}

    # Only compare top chunks to save LLM calls
    previews = "\n\n".join(
        f"[Chunk {i+1}]: {c.text[:400]}"
        for i, c in enumerate(chunks[:4])
    )

    prompt = f"""You are a contradiction detector for a research assistant.
Check if any of these document chunks contradict each other.

{previews}

Reply with JSON only:
{{"contradictions": [
  {{"chunk_a": 1, "chunk_b": 3, "description": "brief description of contradiction"}}
]}}
If no contradictions: {{"contradictions": []}}"""

    try:
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content)
        contradictions = data.get("contradictions", [])
        if contradictions:
            log.info("[contradiction_detector] found %d contradiction(s)", len(contradictions))
            for c in contradictions:
                log.info("  Chunk %s vs Chunk %s: %s",
                         c.get("chunk_a"), c.get("chunk_b"), c.get("description", ""))
        else:
            log.info("[contradiction_detector] no contradictions found")
        return {"contradictions": contradictions}
    except Exception as exc:
        log.warning("[contradiction_detector] failed: %s", exc)
        return {"contradictions": []}


def citation_verifier_node(state: AgentState) -> dict:
    """Verify that citations in the generated answer are supported by the chunks.

    Parses [1], [2] etc. from the answer and checks each cited fact
    against the corresponding chunk text.
    """
    import re
    answer = state.get("answer", "")
    chunks = state.get("chunks", [])
    log.info("[citation_verifier] verifying citations in answer...")

    if not answer or not chunks:
        return {"citation_verified": True}

    # Find cited chunk indices in the answer (e.g. [1], [2])
    cited = set(int(m) for m in re.findall(r'\[(\d+)\]', answer))
    if not cited:
        log.info("[citation_verifier] no citations found in answer")
        return {"citation_verified": True}

    chunk_texts = {i + 1: c.text[:600] for i, c in enumerate(chunks)}
    cited_chunks = {i: chunk_texts[i] for i in cited if i in chunk_texts}

    if not cited_chunks:
        return {"citation_verified": True}

    chunks_preview = "\n\n".join(f"[{i}]: {t}" for i, t in cited_chunks.items())

    prompt = f"""You are a citation verifier. Check if the answer's citations are supported by the source chunks.

Answer: {answer[:800]}

Source chunks:
{chunks_preview}

Reply with JSON only:
{{"verified": true, "unverified": []}}
or
{{"verified": false, "unverified": [1, 3]}}  (list of citation numbers that are NOT supported)"""

    try:
        response = _llm.chat.completions.create(**provider_kwargs(),
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )
        data = json.loads(response.choices[0].message.content)
        unverified = data.get("unverified", [])
        verified = bool(data.get("verified", True))

        if unverified:
            warning = f"\n\n[Note: Citations {unverified} could not be fully verified against the source chunks.]"
            log.info("[citation_verifier] unverified citations: %s", unverified)
            return {"citation_verified": False, "answer": answer + warning}

        log.info("[citation_verifier] all citations verified")
        return {"citation_verified": True}
    except Exception as exc:
        log.warning("[citation_verifier] failed: %s", exc)
        return {"citation_verified": True}


def hallucination_checker_node(state: AgentState) -> dict:
    """Check whether the generated answer is grounded in the retrieved context."""
    log.info("[hallucination_checker] checking if answer is grounded...")
    prompt = f"""You are a hallucination detector. Check if the answer contains only information present in the context.

Context:
{state["context"][:2000]}

Answer:
{state["answer"]}

Reply with JSON only — no explanation:
{{"grounded": true}} or {{"grounded": false}}"""

    response = _llm.chat.completions.create(**provider_kwargs(),
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    try:
        data = json.loads(response.choices[0].message.content)
        has_hallucination = not bool(data.get("grounded", True))
        log.info("[hallucination_checker] result: %s", "HALLUCINATION DETECTED" if has_hallucination else "grounded")
        return {"has_hallucination": has_hallucination}
    except (json.JSONDecodeError, AttributeError):
        log.info("[hallucination_checker] parse failed — defaulting to grounded")
        return {"has_hallucination": False}
