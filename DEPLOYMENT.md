# Deploying Verity (free tier)

Verity runs on a best-of-free managed stack. Each push to `main` auto-deploys.

| Component | Platform | Notes |
|-----------|----------|-------|
| Frontend (Next.js) | **Vercel** | auto-deploys on push |
| Backend + Celery worker | **Hugging Face Spaces** (Docker) | one container; auto-deployed via GitHub Action |
| PostgreSQL | **Neon** | serverless, scale-to-zero |
| Vector DB | **Qdrant Cloud** | free 1 GB cluster |
| Redis (Celery broker) | **Upstash** | `rediss://` TLS |
| LLM | **OpenRouter** | `:free` models |

```
Vercel (frontend) ──HTTP──> HF Space (FastAPI + Celery)
                                  ├──> Neon         (Postgres + FTS)
                                  ├──> Qdrant Cloud (vectors)
                                  ├──> Upstash      (Celery broker)
                                  └──> OpenRouter   (LLM)
```

---

## 1. Prerequisites

Create accounts and collect these values:

| Value | From |
|-------|------|
| `OPENROUTER_API_KEY` | openrouter.ai → Keys |
| `POSTGRES_URL` | Neon → connection string (paste raw; the app converts to asyncpg + TLS) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Qdrant Cloud → cluster endpoint + API key |
| `REDIS_URL` | Upstash → Redis database (the `rediss://…` URL) |

---

## 2. Backend → Hugging Face Space

1. Create a **Docker** Space at huggingface.co (name e.g. `verity-backend`).
2. In the Space → **Settings → Variables and secrets**, add these **secrets**:

   | Secret | Value |
   |--------|-------|
   | `OPENROUTER_API_KEY` | from OpenRouter |
   | `POSTGRES_URL` | from Neon |
   | `QDRANT_URL` | from Qdrant Cloud |
   | `QDRANT_API_KEY` | from Qdrant Cloud |
   | `REDIS_URL` | from Upstash |
   | `CORS_ORIGINS` | your Vercel URL (set after step 3) |
   | `APP_ENV` | `production` |

3. Set up auto-deploy from GitHub — in the **GitHub repo → Settings → Secrets and variables → Actions**:
   - **Secret:** `HF_TOKEN` — a Hugging Face *write* token (huggingface.co → Settings → Access Tokens)
   - **Variable:** `HF_USERNAME` — your HF username
   - **Variable:** `HF_SPACE_NAME` — the Space name (e.g. `verity-backend`)

   The workflow `.github/workflows/deploy-hf.yml` then pushes the backend to the
   Space on every backend change (or run it manually via *Actions → Run workflow*).

4. The Space URL is `https://<HF_USERNAME>-<HF_SPACE_NAME>.hf.space`.
   Verify: open `/<that URL>/health` → `{"status":"ok"}` and `/docs` for the API.

---

## 3. Frontend → Vercel

1. Import the GitHub repo in Vercel. Set **Root Directory** to `frontend`.
2. Add an environment variable:

   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_API_URL` | `https://<HF_USERNAME>-<HF_SPACE_NAME>.hf.space` |

3. Deploy. Copy the resulting Vercel URL and set it as `CORS_ORIGINS` on the HF
   Space (step 2), then restart the Space.

---

## 4. Environment variables reference

Backend (HF Space secrets):

```
OPENROUTER_API_KEY=sk-or-...
POSTGRES_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
QDRANT_URL=https://xxxx.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=...
REDIS_URL=rediss://default:pass@xxx.upstash.io:6379
CORS_ORIGINS=https://your-app.vercel.app
APP_ENV=production
# optional
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
FAST_LLM_MODEL=google/gemma-3-4b-it:free
```

Frontend (Vercel): `NEXT_PUBLIC_API_URL=https://<HF_USERNAME>-<HF_SPACE_NAME>.hf.space`

---

## 5. How auto-deploy works

- **Frontend:** Vercel rebuilds on every push to `main` (native Git integration).
- **Backend:** the GitHub Action pushes the repo to the HF Space, which rebuilds
  the Docker image; `deploy/hf/start.sh` runs `alembic upgrade head`, the Celery
  worker, then Uvicorn on port 7860.

So after the initial setup, **`git push` → both frontend and backend update.**
