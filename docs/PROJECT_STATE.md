# Project State

> Current state of INTYRASENSE as of 2026-09-07.

---

## Purpose

INTYRASENSE is a Retrieval-Augmented Generation (RAG) system for document-grounded Q&A and summarization. Users upload documents (PDF, Markdown, text), which are chunked, embedded, and stored in Supabase pgvector. Queries are answered strictly from retrieved context with confidence scoring and citations.

---

## Architecture

- **Frontend**: Streamlit single-page app (`frontend/app.py`) communicating with the backend via HTTP REST.
- **Backend**: FastAPI (`backend/main.py`) exposing endpoints for upload, query, summarize, documents, and ingestion status.
- **Task Queue**: Celery with Redis broker for background document ingestion. Automatic graceful fallback to `threading.Thread` when Redis is unreachable.
- **Database**: Supabase (PostgreSQL + pgvector) for document metadata, text chunks with vector embeddings, and file storage.
- **LLM**: `openai/gpt-oss-20b` via Groq API (LangChain `ChatGroq`, temperature=0).
- **Embeddings**: `BAAI/bge-small-en-v1.5` via HuggingFace (LangChain `HuggingFaceEmbeddings`, normalized).

---

## Implemented Features

| Feature | Status | Location |
|---|---|---|
| Multi-format upload (PDF, MD, TXT) | ✅ | `backend/main.py` `/upload` |
| Smart PDF loading (native + OCR fallback) | ✅ | `backend/ingest.py` `load_pdf_smart()` |
| SHA-256 deduplication | ✅ | `backend/main.py`, `backend/ingest.py` |
| Recursive text chunking (800/250) | ✅ | `backend/ingest.py` |
| Parallel embedding generation | ✅ | `backend/ingest.py` `embed_parallel()` |
| Celery background ingestion | ✅ | `backend/tasks.py`, `backend/celery_app.py` |
| In-process thread fallback | ✅ | `backend/main.py` (when Redis unavailable) |
| Ingestion status tracking (Redis + in-memory) | ✅ | `backend/state.py` |
| Per-task status with `task_id` | ✅ | `backend/state.py`, `backend/main.py` |
| Conversational Q&A with question rewriting | ✅ | `backend/qa.py` |
| pgvector similarity search via RPC | ✅ | `backend/retriever.py` |
| Query embedding cache (LRU 256) | ✅ | `backend/retriever.py` |
| Confidence gating (< 0.2 rejection) | ✅ | `backend/qa.py` |
| Document summarization (top 15 chunks) | ✅ | `backend/qa.py` |
| Document listing and deletion (cascade) | ✅ | `backend/main.py` |
| Streamlit UI (upload, select, summarize, chat) | ✅ | `frontend/app.py` |
| Docker Compose (backend, frontend, Redis, worker) | ✅ | `Docker/docker-compose.yml` |
| Upstash (cloud TLS Redis) support | ✅ | `backend/celery_app.py` |

---

## Major Components

### Backend (`backend/`)

| File | Purpose |
|---|---|
| `main.py` | FastAPI app, all endpoint definitions, upload/query/summarize/delete |
| `ingest.py` | Full ingestion pipeline: download from Storage → load → chunk → embed → batch insert |
| `qa.py` | RAG orchestration: question rewriting, retrieval, confidence scoring, LLM generation |
| `retriever.py` | pgvector similarity search via Supabase RPC, cached query embeddings |
| `models.py` | Singleton LLM (`ChatGroq`) and embeddings (`HuggingFaceEmbeddings`) via `@lru_cache` |
| `prompts.py` | `SYSTEM_PROMPT` (strict Q&A) and `SUMMARY_PROMPT` templates |
| `supabase_client.py` | Singleton Supabase client with env validation |
| `celery_app.py` | Celery app instance, Redis config, TLS auto-detection, `is_celery_available()` probe |
| `tasks.py` | `ingest_documents_task` Celery task wrapping `ingest_documents()` |
| `state.py` | Ingestion status management: Redis persistence + in-memory fallback |
| `utils.py` | `file_hash()`, `list_documents()`, `get_doc_id_from_name()` |

### Frontend (`frontend/`)

| File | Purpose |
|---|---|
| `app.py` | Complete Streamlit UI: file upload, document selection, summarization, chat Q&A |

---

## Database

### Supabase Tables

- **`documents`**: `id` (UUID PK), `name`, `storage_path`, `type`, `file_hash`
- **`chunks`**: `id` (UUID PK), `source` (FK → documents.id), `page`, `text`, `embedding` (vector)
- **`storage.documents`**: Supabase Storage bucket for raw uploaded files

### Supabase RPC

- **`match_embeddings(query_embedding, match_count, filter_source?)`**: Cosine similarity search returning `text`, `source`, `page`, `score`

---

## Background Services

- **Redis**: Message broker and result backend for Celery. Stores ingestion status (`ingestion:status`, `ingestion:task:{id}`). Keys expire after 24 hours.
- **Celery Worker**: Runs `backend.tasks.ingest_documents_task`. On Windows: `--pool=solo`. In Docker: standard concurrency.
- **Fallback**: If `USE_CELERY=false` or Redis is unreachable, ingestion runs via `threading.Thread` in the FastAPI process.

---

## Deployment

- **Local**: `uvicorn` + `streamlit` + optional Celery worker
- **Docker Compose**: 4 services — `redis`, `celery_worker`, `backend`, `frontend` — on shared bridge network
- **Cloud Redis**: Upstash with `rediss://` URLs; TLS auto-configured in `celery_app.py`
- **Production backend**: Render (current `BACKEND_URL` points to `https://intyrasense.onrender.com`)

---

## Known Limitations

1. **No authentication** — All endpoints are publicly accessible; no user management.
2. **CORS is fully open** — `allow_origins=["*"]` in production is a security risk.
3. **In-memory state is per-process** — Without Redis, ingestion status is lost on backend restart.
4. **Summarization is limited** — Only uses top 15 chunks; large documents may have incomplete summaries.
5. **Single Celery queue** — All tasks go to the default `celery` queue; no priority differentiation.
6. **No retry logic on ingestion failure** — Failed chunks are logged but not retried.
7. **Embedding model loaded at import time** — First startup is slow (~80 MB download + model load).
8. **LLM model string** — `models.py` uses `openai/gpt-oss-20b` via Groq; this is not configurable via env vars.

---

## Recommended Improvements

1. Add authentication (API keys or OAuth) to protect endpoints.
2. Restrict CORS origins for production deployment.
3. Make LLM model name configurable via environment variable.
4. Add Celery task retry with exponential backoff for failed ingestion.
5. Add proper health check endpoint that verifies Supabase and Redis connectivity.
6. Add structured logging (JSON format) for production observability.
7. Implement pagination for `/documents` endpoint.
8. Add file size limits at the API level (currently only enforced in the Streamlit UI at 50MB).

---

## Changes Completed During This Update

### New Files
- `backend/celery_app.py` — Celery application configuration with Redis broker and Upstash TLS support
- `backend/tasks.py` — Celery task for background document ingestion
- `docs/PROJECT_STATE.md` — This file
- `docs/DEVELOPMENT_CONTEXT.md` — Developer onboarding guide
- `docs/CHANGELOG.md` — Change log for this update

### Modified Files
- `backend/main.py` — Added Celery dispatch with thread fallback; `task_id` support on `/upload` and `/ingestion-status`
- `backend/state.py` — Rewritten with Redis persistence, per-task tracking, and in-memory fallback
- `frontend/app.py` — Added `task_id` parameter to ingestion status polling
- `Docker/docker-compose.yml` — Added `redis` and `celery_worker` services with container names and healthcheck
- `Makefile` — Added `worker` target for Celery
- `requirements.txt` — Added `celery` and `redis`
- `backend/requirements.txt` — Added `celery` and `redis`
- `.env.example` — Added Celery/Redis configuration variables with documentation
- `README.md` — Complete rewrite reflecting current codebase
- `docs/ARCHITECTURE.md` — Updated with Celery/Redis architecture
- `docs/SETUP.md` — Updated with Celery worker instructions
- `docs/DEPLOYMENT.md` — Updated Docker section with Redis and Celery worker
