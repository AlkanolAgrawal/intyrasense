# Development Context

> Developer onboarding guide for INTYRASENSE. Describes the architecture, data flows, design decisions, and operational details needed to work on the codebase.

---

## Repository Layout

```
intyrasense/
├── backend/                  # FastAPI backend (Python)
│   ├── main.py               # App entry point, all REST endpoints
│   ├── ingest.py             # Document ingestion pipeline
│   ├── qa.py                 # RAG Q&A + summarization logic
│   ├── retriever.py          # Vector similarity search
│   ├── models.py             # LLM and embedding model singletons
│   ├── prompts.py            # LLM prompt templates
│   ├── supabase_client.py    # Supabase client singleton
│   ├── celery_app.py         # Celery configuration and Redis probe
│   ├── tasks.py              # Celery task definitions
│   ├── state.py              # Ingestion status management
│   ├── utils.py              # Shared utilities
│   └── requirements.txt      # Backend-specific dependencies
├── frontend/                 # Streamlit frontend (Python)
│   ├── app.py                # Complete UI: upload, select, summarize, chat
│   └── requirements.txt      # Frontend-specific dependencies
├── Docker/                   # Containerization
│   ├── docker-compose.yml    # 4-service stack
│   ├── Dockerfile.backend    # Python 3.11 + OCR system deps
│   └── Dockerfile.frontend   # Python 3.11 slim
├── docs/                     # Documentation
├── .env.example              # Template for environment configuration
├── Makefile                  # Developer shortcuts
└── requirements.txt          # Root-level unified dependencies
```

---

## Configuration

### Environment Variables

All configuration is done via a `.env` file (loaded by `python-dotenv`). See `.env.example` for the full list.

**Required:**

| Variable | Used By |
|---|---|
| `GROQ_API_KEY` | `backend/models.py` — LLM inference via Groq API |
| `SUPABASE_URL` | `backend/supabase_client.py`, `backend/main.py` — Database and storage |
| `SUPABASE_KEY` | `backend/supabase_client.py`, `backend/main.py` — Database and storage |

**Optional:**

| Variable | Default | Used By |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | `frontend/app.py` |
| `USE_CELERY` | `true` | `backend/celery_app.py` |
| `REDIS_URL` | `redis://localhost:6379/0` | `backend/celery_app.py`, `backend/state.py` |
| `CELERY_BROKER_URL` | Value of `REDIS_URL` | `backend/celery_app.py` |
| `CELERY_RESULT_BACKEND` | Value of `REDIS_URL` | `backend/celery_app.py` |

---

## Data Flow

### Document Upload & Ingestion

```
1. User selects files in Streamlit → clicks "Upload & Index"
2. Streamlit sends POST /upload (multipart/form-data) to FastAPI
3. FastAPI:
   a. Reads each file, computes SHA-256 hash
   b. Constructs unique name: {hash}_{filename}
   c. Skips if already exists in Supabase Storage bucket
   d. Uploads new files to Supabase Storage "documents" bucket
4. Dispatches ingestion:
   a. If Celery available → ingest_documents_task.delay(files)
      - Sets ingestion status to "running" with task_id
   b. Else → threading.Thread(target=ingest_documents, args=(files,))
      - Sets ingestion status to "running" (no task_id)
5. Ingestion pipeline (ingest.py):
   a. Downloads each file from Supabase Storage
   b. Computes hash → checks "documents" table for duplicates
   c. Inserts document record (name, type, storage_path, file_hash)
   d. Loads content: PyPDFLoader → if < 100 chars, OCR fallback (Tesseract)
   e. Splits into 800-char chunks (250 overlap) via RecursiveCharacterTextSplitter
   f. Filters out chunks < 20 chars
   g. Generates embeddings in parallel batches (64 texts, 4 workers)
   h. Batch inserts into "chunks" table (1000 records per batch)
   i. Sets status to "completed" or "failed"
6. Streamlit polls GET /ingestion-status?task_id=... every 2 seconds
```

### Question Answering (RAG)

```
1. User types question in Streamlit chat → POST /query
2. qa.py:
   a. rewrite_question(): If chat_history exists, uses LLM to make question standalone
   b. get_doc_id_from_name(): Resolves document name to UUID (if scoped)
   c. retrieve_with_score(): Calls match_embeddings RPC with query embedding
      - Returns top 10 chunks with cosine similarity scores
   d. Selects top 5 results
   e. If max(similarity) < 0.2 → returns "Not found" with confidence 0
   f. Builds context from chunk texts
   g. Formats SYSTEM_PROMPT with context + question
   h. Invokes LLM → extracts answer
   i. Builds citations: document_name — page N
   j. Returns { answer, citations[], confidence }
```

### Document Summarization

```
1. User clicks "Summarize Document" → POST /summarize
2. qa.py:
   a. Queries chunks table, filtered by document UUID (if scoped)
   b. Limits to 15 chunks (context window constraint)
   c. Formats SUMMARY_PROMPT with combined chunk text
   d. Invokes LLM → returns summary + citations
```

### Document Deletion

```
1. User clicks delete button → DELETE /documents/{doc_id}
2. main.py:
   a. Looks up document record by UUID
   b. Deletes all chunks where source = doc_id
   c. Removes file from Supabase Storage
   d. Deletes document record
```

---

## Background Task Architecture

### Celery + Redis

The system uses Celery for background processing of document ingestion. Redis serves as both the message broker (task queue) and the result backend (task state storage).

**Configuration (`celery_app.py`):**

- App name: `intyrasense`
- Serializer: JSON
- Task tracking: enabled (`task_track_started=True`)
- Result expiry: 3600 seconds (1 hour)
- TLS: Auto-configured for `rediss://` URLs (Upstash)

**Availability probe (`is_celery_available()`):**

1. Checks `USE_CELERY` env var
2. Attempts `redis.Redis.from_url(CELERY_BROKER_URL).ping()` with 3-second timeout
3. Returns `True` only if both checks pass

**Task flow:**

```
main.py /upload
  └─ is_celery_available()?
      ├─ Yes → ingest_documents_task.delay(files)
      │        └─ task_id returned
      └─ No → threading.Thread(ingest_documents)
              └─ no task_id
```

### Ingestion Status (`state.py`)

Status is tracked at two levels:

1. **Global**: `ingestion:status` Redis key — tracks the latest ingestion state
2. **Per-task**: `ingestion:task:{task_id}` Redis key — tracks individual Celery task state

Both keys expire after 24 hours. If Redis is unavailable, status falls back to a module-level Python dict (`_in_memory_status`).

**Status retrieval priority:**

1. If `task_id` provided → check `AsyncResult` via Celery backend → fallback to Redis key
2. Check global Redis key
3. Fallback to in-memory dict

---

## External Services

### Supabase

- **PostgreSQL + pgvector**: Stores document metadata and text chunks with vector embeddings
- **Storage**: Hosts uploaded files in the `documents` bucket
- **RPC**: `match_embeddings()` function for vector similarity search
- **Client**: Initialized once as a global singleton in `supabase_client.py`

### Groq API

- **Model**: `openai/gpt-oss-20b` (temperature=0)
- **Usage**: Question answering and summarization via LangChain `ChatGroq`
- **No local GPU needed** — inference runs on Groq's servers

### Redis (Upstash or local)

- **Broker**: Celery task queue distribution
- **Backend**: Celery task result storage
- **State**: Ingestion status persistence
- **TLS**: Automatically enabled when URL scheme is `rediss://`

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Supabase pgvector over FAISS | Managed, persistent, SQL-queryable, no local state files to manage |
| SHA-256 filename prefix | Prevents duplicate uploads at the storage layer before any processing |
| Double dedup check (storage + DB) | Storage-level skip in `main.py` + DB hash check in `ingest.py` for safety |
| `is_celery_available()` probe | Zero-breakage design: if Redis is down, everything still works via threads |
| In-memory status fallback | Ensures status polling works even without Redis running |
| `@lru_cache` on models | Singleton pattern prevents re-initialization of expensive LLM/embedding models |
| `embed_query_cached()` (LRU 256) | Avoids re-embedding identical queries during a single process lifecycle |
| Confidence threshold 0.2 | Below this, cosine similarity is too low to produce useful answers |
| Top-5 chunks for Q&A | Balances context quality with LLM token budget |
| Top-15 chunks for summarization | Fits within context window while covering key document content |
| `-P solo` for Windows workers | `fork` is not available on Windows; `solo` is the safest pool type |
| Batch insert (1000/batch) | Prevents Supabase API timeouts on large documents |

---

## Running Locally

### Minimal setup (no Redis)

```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload

# Terminal 2: Frontend
streamlit run frontend/app.py
```

Ingestion will run via in-process threads. No Celery worker needed.

### Full setup (with Redis)

```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload

# Terminal 2: Frontend
streamlit run frontend/app.py

# Terminal 3: Celery worker
celery -A backend.celery_app.celery worker --loglevel=info -P solo
```

### Docker Compose (all services)

```bash
docker compose -f Docker/docker-compose.yml up --build
```

Starts: Redis → Celery worker → Backend → Frontend

---

## Debugging Tips

### Check Redis state

```bash
# Connect to Redis CLI
redis-cli
# Or for Upstash: redis-cli -u rediss://default:PASSWORD@HOST:PORT

# Check ingestion status
GET ingestion:status

# Check a specific task
GET ingestion:task:<task_id>

# See Celery internal keys (Kombu routing)
KEYS _kombu*
```

### Check Celery task state

```python
from celery.result import AsyncResult
from backend.celery_app import celery

result = AsyncResult("task-id-here", app=celery)
print(result.state)  # PENDING, STARTED, RUNNING, SUCCESS, FAILURE
print(result.info)   # task metadata
```

### Common issues

| Issue | Cause | Fix |
|---|---|---|
| `GROQ_API_KEY not set` | Missing `.env` file | Copy `.env.example` → `.env`, fill in values |
| `SUPABASE_URL not set` | Missing `.env` file | Same as above |
| Backend not reachable | Frontend started before backend | Start backend first |
| Ingestion stuck at "running" | Worker not running or Redis unreachable | Start Celery worker or set `USE_CELERY=false` |
| `_kombu` keys in Redis | Normal Celery internals | Not a bug — these are Kombu routing tables |
| `ssl_cert_reqs` errors | Missing TLS config for `rediss://` | Already handled in `celery_app.py`; ensure URL starts with `rediss://` |
| Slow first startup | Embedding model download (~80 MB) | One-time only; cached after first download |
