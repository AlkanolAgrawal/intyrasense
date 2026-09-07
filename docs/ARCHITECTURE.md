# 🏗️ Architecture

> Detailed architecture documentation for INTYRASENSE.

---

## Overview

INTYRASENSE is a **Retrieval-Augmented Generation (RAG)** system with a strict no-hallucination policy. It uses a multi-service architecture:

- **FastAPI backend** — Document processing, LLM orchestration, REST API
- **Streamlit frontend** — User interface for upload, search, summarization, and chat
- **Celery + Redis** — Background task queue for document ingestion (with graceful fallback)
- **Supabase** — PostgreSQL database (pgvector), file storage, and vector similarity search

```text
┌───────────────────────────────────────────────────────────────────────┐
│  Streamlit Frontend (port 8501)                                       │
│  Upload │ Select Document │ Summarize │ Chat Q&A                      │
└──────────────────┬────────────────────────────────────────────────────┘
                   │  HTTP/REST
┌──────────────────▼────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                          │
│                                                                       │
│  POST /upload ──► Celery task queue OR in-process thread              │
│  POST /query  ──► RAG pipeline (rewrite → retrieve → LLM answer)     │
│  POST /summarize ──► Summarization pipeline                           │
│  GET  /documents ──► List from Supabase                               │
│  DELETE /documents/{id} ──► Cascade delete                            │
│  GET  /ingestion-status ──► Redis or in-memory state                  │
└──────────────────┬──────────────────────┬─────────────────────────────┘
                   │                      │
┌──────────────────▼──────┐   ┌───────────▼─────────────────────────────┐
│  Redis (Upstash/local)  │   │  Supabase                               │
│  ├─ Celery broker       │   │  ├─ Storage: "documents" bucket         │
│  ├─ Celery result store │   │  ├─ Table: documents (metadata + hash)  │
│  └─ Ingestion status    │   │  ├─ Table: chunks (text + embedding)    │
└─────────────────────────┘   │  └─ RPC: match_embeddings() (pgvector)  │
                              └─────────────────────────────────────────┘
```

---

## Components

### 1. Frontend — Streamlit (`frontend/app.py`)

The frontend provides an interactive web UI with four main sections:

| Section | Functionality |
|---------|--------------|
| **Upload** | File upload widget accepting PDF, Markdown, and text files (50 MB limit per file) |
| **Document Selection** | Dropdown to scope queries to a specific document or all documents |
| **Summarization** | One-click summary generation for selected documents |
| **Chat (Q&A)** | Conversational interface with chat history, confidence scores, and citations |

Communication with the backend is done via `requests` HTTP calls to the FastAPI REST API. The `BACKEND_URL` is configurable via environment variable (defaults to `http://localhost:8000`).

After upload, the frontend polls `GET /ingestion-status?task_id=...` every 2 seconds with a 10-minute timeout.

### 2. Backend — FastAPI (`backend/`)

#### `main.py` — API Layer

Defines eight endpoints:

| Endpoint | Method | Function |
|---|---|---|
| `/` | GET | Health check: `{ status: "running" }` |
| `/` | HEAD | Health check: 200 OK |
| `/upload` | POST | File upload → Supabase Storage → ingestion dispatch |
| `/ingestion-status` | GET | Ingestion status (global or per-task via `task_id` param) |
| `/query` | POST | RAG question answering |
| `/summarize` | POST | Document summarization |
| `/documents` | GET | List all indexed documents |
| `/documents/{doc_id}` | DELETE | Delete document + chunks + storage file |

The upload endpoint performs deduplication at the storage layer (skips existing filenames), then dispatches ingestion via Celery or in-process thread.

#### `ingest.py` — Document Ingestion Pipeline

```text
Download from Storage → Load (PDF/MD/TXT) → OCR Fallback → Chunk → Embed → Batch Insert
```

Key behaviors:
- **Smart PDF loading**: Tries native text extraction first (`PyPDFLoader`), falls back to Tesseract OCR if native text is < 100 characters
- **Duplicate check**: SHA-256 hash compared against `documents` table before processing
- **Recursive chunking**: `RecursiveCharacterTextSplitter` (800 chars, 250 overlap)
- **Minimum chunk filter**: Discards chunks shorter than 20 characters
- **Parallel embedding**: `ThreadPoolExecutor` with 4 workers, 64 texts per batch
- **Batch insert**: 1000 records per Supabase insert to avoid API timeouts

#### `retriever.py` — Vector Retrieval

- Queries Supabase `match_embeddings()` RPC function for cosine similarity search
- Embedding model (`BAAI/bge-small-en-v1.5`) loaded at module level (singleton via `@lru_cache`)
- Query embeddings cached with `@lru_cache(maxsize=256)` — lowercased and stripped before hashing
- Supports filtered retrieval (by `filter_source` document UUID) or global search
- Returns top-k results (default: 10) with cosine similarity scores

#### `qa.py` — Question Answering & Summarization

**Q&A Pipeline:**

1. **Question rewriting** — Rewrites follow-up questions into standalone queries using the last 3 Q&A pairs via LLM
2. **Retrieval** — Fetches top-10 chunks, selects top-5 for context
3. **Confidence scoring** — `confidence = max(similarity_scores)`, clamped to [0, 1]
4. **Confidence gating** — Rejects answers with confidence < 0.2 as "Not found in internal documents"
5. **Answer generation** — LLM generates answer using strict `SYSTEM_PROMPT` (no external knowledge)
6. **Citation extraction** — Extracts document name + page number from chunk metadata

**Summarization Pipeline:**

- Fetches top 15 chunks for the selected document (or across all documents)
- Single-pass summarization via `SUMMARY_PROMPT`
- Returns summary + source document citations

#### `prompts.py` — System Prompts

Contains two prompt templates:
- `SYSTEM_PROMPT` — Strict Q&A prompt that forbids external knowledge, hallucination, and citation in answer text
- `SUMMARY_PROMPT` — Summarization prompt requiring source-grounded statements with `(DocumentName — Page X)` citations

#### `models.py` — LLM & Embeddings

| Component | Implementation | Configuration |
|---|---|---|
| LLM | `langchain_groq.ChatGroq` | Model: `openai/gpt-oss-20b`, temperature: 0 |
| Embeddings | `langchain_huggingface.HuggingFaceEmbeddings` | Model: `BAAI/bge-small-en-v1.5`, normalized |

Both are lazily initialized via `@lru_cache(maxsize=1)` — created on first use and reused for the process lifetime.

#### `supabase_client.py` — Database Client

- Validates `SUPABASE_URL` and `SUPABASE_KEY` at import time (fails fast with `RuntimeError`)
- Creates a singleton `Client` instance used by all backend modules

#### `celery_app.py` — Task Queue Configuration

- Celery app named `intyrasense` with JSON serialization
- Broker and backend default to `REDIS_URL` env var
- Auto-detects `rediss://` URLs and applies `ssl_cert_reqs=CERT_REQUIRED` for TLS (Upstash support)
- `is_celery_available()` probe: checks `USE_CELERY` flag + pings Redis with 3-second timeout

#### `tasks.py` — Celery Tasks

- Single task: `ingest_documents_task` — wraps `ingest_documents()` with Celery state tracking
- Updates task state to `RUNNING` → `SUCCESS`/`FAILURE`
- Sets ingestion status via `state.py` for status polling

#### `state.py` — Ingestion Status

Dual-backend status tracking:

1. **Redis** (primary): `ingestion:status` (global) and `ingestion:task:{task_id}` (per-task), 24h TTL
2. **In-memory dict** (fallback): Module-level `_in_memory_status` dict

Redis connection is lazy and cached — first call attempts connection, failure sets `_redis_client = False` permanently for the process.

#### `utils.py` — Utilities

- `file_hash(data: bytes)` — SHA-256 hex digest
- `list_documents()` — Queries `documents` table, returns sorted by name
- `get_doc_id_from_name(name)` — Resolves `storage_path` to document UUID

### 3. Data Layer (Supabase)

| Resource | Purpose |
|----------|---------|
| `documents` table | Metadata: `id` (UUID PK), `name`, `storage_path`, `type`, `file_hash` |
| `chunks` table | Text chunks: `id` (UUID PK), `source` (FK → documents.id), `page`, `text`, `embedding` (vector) |
| `storage.documents` bucket | Raw uploaded files named `{sha256}_{filename}` |
| `match_embeddings()` RPC | pgvector cosine similarity search: `(query_embedding, match_count, filter_source?)` → `(text, source, page, score)` |

### 4. Task Queue Layer (Redis + Celery)

- **Redis** serves three roles: Celery message broker, Celery result backend, and ingestion status store
- **Celery worker** process runs `ingest_documents_task` in a separate process
- **Fallback**: When Redis is unreachable or `USE_CELERY=false`, ingestion runs in a daemon `threading.Thread` within the FastAPI process

### 5. Containerization (`Docker/`)

| Service | Image | Port | Depends On |
|---------|-------|------|------------|
| `redis` | `redis:7-alpine` | 6379 | — |
| `celery_worker` | `Dockerfile.backend` | — | redis (healthy) |
| `backend` | `Dockerfile.backend` | 8000 | redis (healthy) |
| `frontend` | `Dockerfile.frontend` | 8501 | backend |

- All services share the `intyrasense-network` bridge network
- Redis, broker, and backend URLs are overridden to use container-internal DNS (`redis://redis:6379/0`)
- **`Dockerfile.backend`** — Python 3.11 + Tesseract + Poppler system dependencies
- **`Dockerfile.frontend`** — Python 3.11 slim

---

## Data Flow

### Document Upload Flow

```text
User uploads file(s) via Streamlit
  → POST /upload (multipart/form-data)
    → For each file:
        → Compute SHA-256 hash
        → Construct unique name: {hash}_{filename}
        → Skip if already in Supabase Storage bucket
        → Upload to Supabase Storage "documents" bucket
    → Dispatch ingestion:
        → If Celery available:
            → ingest_documents_task.delay(uploaded_files)
            → Return { task_id, message }
        → Else:
            → threading.Thread(target=ingest_documents)
            → Return { message }
    → Ingestion pipeline:
        → Download from Supabase Storage
        → Check documents table for duplicate hash
        → Insert document record
        → Load content (PyPDFLoader / OCR / TextLoader / MarkdownLoader)
        → RecursiveCharacterTextSplitter (800 chars, 250 overlap)
        → Filter chunks < 20 chars
        → embed_parallel() with ThreadPoolExecutor (4 workers, 64/batch)
        → Batch insert into Supabase chunks table (1000/batch)
        → Set status to "completed" or "failed"
```

### Question Answering Flow

```text
User types question in chat
  → POST /query { question, chat_history, document }
    → rewrite_question() — standalone query from follow-up
    → retrieve_with_score() — Supabase pgvector via match_embeddings RPC (k=10)
    → Select top 5 results
    → Calculate confidence = max(similarity scores)
    → If confidence < 0.2: reject as "Not found"
    → Build context from retrieved chunk texts
    → LLM generates answer with SYSTEM_PROMPT
    → Build citations: document_name — page N
    → Return { answer, citations, confidence }
```

### Summarization Flow

```text
User clicks "Summarize Document"
  → POST /summarize { document }
    → Query chunks table (filtered by document, limited to 15)
    → Build context from chunk texts
    → LLM generates summary with SUMMARY_PROMPT
    → Build citations from source document names
    → Return { summary, citations }
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Supabase + pgvector** | Managed PostgreSQL with vector extension; persistent, SQL-native, no local state files |
| **BGE-small-en-v1.5** | High-quality embeddings with reasonable inference latency; ~80 MB model size |
| **Groq API** | Extremely fast inference for LLM; no local GPU needed; free tier available |
| **Celery + Redis** | Scalable background processing; decouples ingestion from API request lifecycle |
| **Graceful fallback** | `is_celery_available()` probe ensures the system works without Redis via in-process threads |
| **SHA-256 deduplication** | Prevents redundant processing at both storage and database levels |
| **Batch insertion (1000)** | Efficient document ingestion; prevents Supabase API timeouts |
| **Strict system prompt** | Core requirement — prevents hallucination and ensures source grounding |
| **Confidence threshold (0.2)** | Prevents low-quality answers from reaching the user |
| **Top-5 chunks for Q&A** | Balances context quality with LLM token budget |
| **Top-15 chunks for summarization** | Fits within context window while covering key document content |
| **`@lru_cache` singletons** | Prevents re-initialization of expensive LLM and embedding models |
| **In-memory status fallback** | Ensures status polling works even without Redis |
