# Changelog

All notable changes to INTYRASENSE are documented in this file.

---

## [Unreleased] — 2026-09-07

### Added

- **Celery task queue** for background document ingestion (`backend/celery_app.py`, `backend/tasks.py`)
  - Dispatches `ingest_documents_task` via Celery when Redis is available
  - Automatic graceful fallback to `threading.Thread` when Redis is unreachable
  - `is_celery_available()` probe with 3-second Redis ping timeout
  - Cloud Redis (Upstash) TLS auto-configuration for `rediss://` URLs
  - SSL certificate requirements auto-applied for broker and backend connections
- **Redis-backed ingestion status** (`backend/state.py`)
  - Global status key (`ingestion:status`) and per-task keys (`ingestion:task:{task_id}`)
  - 24-hour key expiry
  - In-memory dict fallback when Redis is unavailable
  - Status retrieval priority: Celery `AsyncResult` → Redis key → in-memory dict
- **Per-task status tracking** via `task_id` parameter
  - `POST /upload` returns `task_id` when Celery dispatches successfully
  - `GET /ingestion-status?task_id=...` queries individual task state
  - Frontend polls with `task_id` for accurate per-upload status
- **Docker Compose services** for Redis and Celery worker
  - `redis` service: Redis 7 Alpine with healthcheck
  - `celery_worker` service: Reuses backend image, runs worker process
  - Container names: `intyrasense-redis`, `intyrasense-celery-worker`
  - Worker waits for Redis healthcheck before starting
- **Makefile `worker` target**: `celery -A backend.celery_app.celery worker --loglevel=info -P solo`
- **Environment variables**: `USE_CELERY`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- **Dependencies**: `celery`, `redis` added to `requirements.txt` and `backend/requirements.txt`

### Changed

- **`backend/main.py`**: Upload endpoint now attempts Celery dispatch before thread fallback; returns `task_id` in response
- **`backend/state.py`**: Complete rewrite — replaced simple dict with Redis-persistent state management
- **`frontend/app.py`**: Ingestion status polling now passes `task_id` query parameter
- **`Docker/docker-compose.yml`**: Added `redis`, `celery_worker` services; added container names and bridge network
- **`.env.example`**: Added Celery/Redis configuration section with documentation

### Documentation

- **`README.md`**: Complete rewrite covering full architecture, Celery/Redis, database schema, all API endpoints
- **`docs/ARCHITECTURE.md`**: Updated with Celery/Redis layer, corrected data flow diagrams
- **`docs/SETUP.md`**: Added Celery worker setup, Redis requirements, Windows `-P solo` notes
- **`docs/DEPLOYMENT.md`**: Updated Docker section with 4-service stack, corrected service table
- **`docs/PROJECT_STATE.md`**: New — comprehensive project state snapshot
- **`docs/DEVELOPMENT_CONTEXT.md`**: New — developer onboarding, data flows, debugging guide
- **`docs/CHANGELOG.md`**: New — this file

---

## [1.0.0] — Initial Release

### Features

- Multi-format document upload (PDF, Markdown, plain text)
- Smart PDF loading with OCR fallback (Tesseract + Poppler)
- SHA-256 content deduplication
- Recursive text chunking (800 char / 250 overlap)
- Parallel embedding generation (`BAAI/bge-small-en-v1.5`)
- Supabase pgvector similarity search via `match_embeddings` RPC
- RAG-based question answering with confidence scoring
- Conversational context (question rewriting from last 3 Q&A turns)
- Document summarization (context-window-limited, top 15 chunks)
- Document management (list, delete with cascade)
- Streamlit web UI with upload, document selection, summarize, and chat
- Docker Compose deployment (backend + frontend)
- Health check endpoints (`GET /`, `HEAD /`)
