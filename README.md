# Verity

A production-grade, learning-focused RAG (Retrieval-Augmented Generation) platform built from scratch. Designed to deeply understand every layer of modern RAG systems — from dense retrieval to agentic pipelines.

---

## What It Does

Verity lets you ingest research papers and ask questions about them. Instead of reading 20 papers manually, you ask a question and the system synthesizes answers from your knowledge base.

```
You: "What are the main approaches to reduce hallucinations in RAG?"

Verity: [reads 5 relevant chunks from ingested papers]
  "Three main approaches exist:
   1. Retrieval grounding — constrain LLM to context only [1]
   2. Hallucination detection — checker agent flags ungrounded claims [2]
   3. RAPTOR summaries — broad cluster summaries for better coverage [3]"
```

---

## Architecture

```
[User Query]
     ↓
[Planner Agent]          ← decides approach, generates sub-queries
     ↓
[Hybrid Retriever]
  ├── HyDE Dense (Qdrant)    ← hypothetical document embedding
  ├── Sparse BM25 (Postgres) ← keyword full-text search
  └── Graph Entity (Qdrant)  ← entity-overlap matching
     ↓
[RRF Fusion → Cross-Encoder Rerank]
     ↓
[Grader Agent]           ← relevant? → continue / no → web search
     ↓
[Contradiction Detector] ← flags conflicting claims between chunks
     ↓
[Generator]              ← Llama 3.3 70B (OpenRouter), streaming SSE
     ↓
[Citation Verifier]      ← checks [1][2] citations against source chunks
     ↓
[Hallucination Checker]  ← answer grounded in context?
     ↓
[Streaming Response]
```

> This is the full `/research/query` agentic pipeline. The chat UI calls
> `/research/query/stream` — a latency-optimized subset: dense + sparse retrieval,
> RRF fusion and cross-encoder reranking, then streamed generation (the grader /
> contradiction / citation / hallucination agents run only on `/research/query`).

Full flow diagrams → [`Architecture/FLOW_DIAGRAM.md`](Architecture/FLOW_DIAGRAM.md)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| Agent Orchestration | LangGraph |
| LLM | Llama 3.3 70B via OpenRouter |
| Vision | Llama 4 Scout via OpenRouter |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL + SQLAlchemy |
| Full-text Search | PostgreSQL FTS (tsvector + GIN) |
| Embeddings | BAAI/bge-small-en-v1.5 (local ONNX via fastembed, no API key) |
| Reranking | Cross-encoder ms-marco-MiniLM-L-6-v2 (ONNX via fastembed, no torch) |
| Task Queue | Celery + Redis |
| Tracing | Langfuse (optional, generation span) |
| Evaluation | LLM-as-judge (faithfulness, relevancy, context recall/precision) |
| Auth | JWT (bcrypt + HS256), per-user KB isolation |
| Frontend | Next.js 16 + Tailwind + shadcn/ui |
| Deployment | Docker Compose · HF Spaces + Vercel (free tier) |

---

## Features

**Retrieval**
- Hybrid retrieval — dense + sparse fused with Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking — RRF candidates rescored by a relevance cross-encoder (ONNX, no torch)
- HyDE — query expanded to hypothetical answer before embedding
- Graph RAG — entity extraction + entity-overlap retrieval
- RAPTOR — cluster summaries for broad questions
- Confidence threshold — low score triggers web search fallback

**Ingestion**
- PDF, DOCX, TXT, Markdown, Web URLs
- Text cleaning — removes emails, DOIs, references, copyright noise
- Multi-modal — PDF image extraction + vision-LLM descriptions (Llama 4 Scout via OpenRouter)
- Hash deduplication — same file ingested twice → instant skip
- Async ingestion via Celery for large documents

**Agents (LangGraph)**
- Planner — query complexity analysis, sub-query decomposition
- Grader — LLM relevance check
- Contradiction Detector — flags conflicting claims between sources
- Generator — context-grounded answer with streaming SSE
- Citation Verifier — verifies [1][2] references against chunks
- Hallucination Checker — answer grounded in retrieved context? *(full `/query` path; skipped in streaming for latency)*
- Web Search Agent — Tavily/DuckDuckGo fallback, auto-ingests into KB

**Memory**
- Short-term — in-memory session cache
- Long-term — Postgres-backed conversation history per session

**Auth & Isolation**
- JWT authentication (bcrypt + HS256) — register / login / protected routes
- Per-user knowledge base — every document, chunk and conversation is scoped to its owner
- In-chat upload — attach a paper from the chat box; it starts a new chat named after it
- Per-user rate limiting on the streaming query endpoint

---

## Roadmap

Honest status of components that are designed but not yet shipped:

- 📋 **True semantic chunking** — planned. The semantic chunker currently falls back to recursive splitting.
- 📋 **Full-pipeline tracing** — planned. Langfuse currently traces the generation step only.
- 📋 **Graph retrieval on by default** — entity extraction is implemented but off by default (it adds an LLM call per chunk at ingest time); enable with `ENABLE_ENTITY_EXTRACTION=true`.

---

## Quick Start

**1. Clone and setup**
```bash
git clone https://github.com/abhi13jaat/Verity.git
cd Verity
python -m venv venv
source venv/bin/activate     # macOS / Linux
# venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

**2. Environment variables**

Create `.env` file:
```env
OPENROUTER_API_KEY=sk-or-...
# Required — signs JWT auth tokens. Generate one with: openssl rand -hex 32
JWT_SECRET_KEY=replace-with-a-32-byte-hex-secret
# Ports below match the docker-compose host mappings (5433 / 6380)
POSTGRES_URL=postgresql+asyncpg://postgres:password@localhost:5433/verity
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6380/0

# Optional
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
FAST_LLM_MODEL=google/gemma-3-4b-it:free
TAVILY_API_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
CORS_ORIGINS=http://localhost:3000
```

**3. Start infrastructure**
```bash
docker-compose up postgres redis qdrant -d
```

**4. Run migrations**
```bash
alembic upgrade head
```

**5. Start backend**
```bash
uvicorn main:app --reload
```

**6. Start frontend** (new terminal)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`

---

## Deployment

**Local (one command):**
```bash
docker-compose up --build
```
Starts everything: Postgres, Qdrant, Redis, backend (with auto-migration), Celery worker, frontend.

**Free-tier cloud** — Vercel (frontend) + Hugging Face Spaces (backend + worker) + Neon (Postgres) + Qdrant Cloud + Upstash (Redis), auto-deployed on push → see [`DEPLOYMENT.md`](DEPLOYMENT.md).

---

## Ingest Papers

```bash
python -m scripts.arxiv_ingest --query "retrieval augmented generation" --max 10 --domain ml
```

Build RAPTOR summaries after ingestion:
```bash
python -m scripts.build_raptor --domain ml
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create an account → returns JWT |
| POST | `/auth/login` | Log in → returns JWT |
| GET | `/auth/me` | Current authenticated user |
| POST | `/research/upload` | Upload a file (multipart) → ingest into your KB |
| POST | `/research/ingest` | Sync ingest from a path/URL |
| POST | `/research/ingest/async` | Async ingest via Celery |
| GET | `/research/tasks/{id}` | Check async task status |
| POST | `/research/query` | Query knowledge base (full agentic) |
| POST | `/research/query/stream` | Streaming query (SSE) |
| GET | `/research/sessions` | List the user's chat sessions |

All `/research/*` routes require an `Authorization: Bearer <token>` header.

Interactive docs: `http://localhost:8000/docs`

---

## Project Structure

```
Verity/
├── backend/
│   ├── agents/          # LangGraph nodes + graph
│   ├── api/             # FastAPI routes + schemas
│   ├── core/            # Config + settings
│   ├── db/              # SQLAlchemy models
│   ├── ingestion/       # Parsers, chunkers, cleaning, embedding
│   │   ├── cleaning/    # Text noise removal
│   │   ├── graph/       # Entity extraction
│   │   ├── multimodal/  # PDF image → vision LLM
│   │   └── raptor/      # Cluster summarization
│   ├── memory/          # Conversation history store
│   ├── retrieval/       # Dense, sparse, hybrid, HyDE, graph
│   └── workers/         # Celery tasks
├── frontend/            # Next.js chat + ingest UI
├── migrations/          # Alembic DB migrations
├── scripts/             # arxiv ingest, RAPTOR builder, KB reset
├── tests/               # Unit + evaluation tests
├── Architecture/        # System design docs + flow diagrams
├── docker-compose.yml
└── Dockerfile
```

---

## Evaluation

An LLM-as-judge harness scores the pipeline on four metrics — **faithfulness,
answer relevancy, context recall, context precision** — over a golden Q/A set,
and compares retrieval **without vs with** the cross-encoder reranker.

```bash
python -m scripts.run_eval
```

Prints a baseline-vs-reranker table and writes `reports/eval_report.json`.

**Results** — 20 hand-curated Q/A pairs over a 13-paper RAG corpus
(1,069 chunks), judged by Llama 3.3 70B:

| Metric | Baseline (RRF) | + Cross-Encoder Reranker | Δ |
|--------|:--------------:|:------------------------:|:---:|
| Context Recall | 0.32 | **0.45** | **+41%** |
| Context Precision | 0.63 | **0.73** | **+16%** |
| Faithfulness | 0.865 | **0.89** | +3% |
| Answer Relevancy | 0.97 | 0.97 | — |

The cross-encoder reranker delivers its largest gains exactly where expected —
**retrieval quality** (recall +41%, precision +16%) — by rescoring RRF-fused
candidates on joint query–document relevance. Answer relevancy is already at
ceiling, so the lift shows up in the retrieval-side metrics. (Δ shown as relative
change; deltas vary run-to-run since the judge is an LLM.)
