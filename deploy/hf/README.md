---
title: Verity Backend
emoji: 🔎
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Verity — Backend (API + Celery worker)

FastAPI + LangGraph agentic RAG backend for
[**Verity**](https://github.com/anuragchaubey1224/Verity).

This Space is **auto-deployed from GitHub** via a GitHub Action — do not edit it
directly. Configure secrets under **Settings → Variables and secrets**:

| Secret | From |
|--------|------|
| `OPENROUTER_API_KEY` | openrouter.ai |
| `POSTGRES_URL` | Neon |
| `QDRANT_URL` + `QDRANT_API_KEY` | Qdrant Cloud |
| `REDIS_URL` | Upstash |
| `CORS_ORIGINS` | your Vercel frontend URL |
| `APP_ENV` | `production` |

Interactive API docs: `/docs` · health check: `/health`
