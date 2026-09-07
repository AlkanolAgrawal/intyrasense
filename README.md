<div align="center">

# INTYRASENSE

**Document-grounded Q&A and summarization over unstructured data.**  
Upload PDFs, Markdown, or text files — ask questions, get sourced answers.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## Overview

INTYRASENSE is a **Retrieval-Augmented Generation (RAG)** system that lets users upload internal documents and query them through a conversational interface. It enforces strict source grounding — the LLM only answers from retrieved context, never from its training data. Each answer includes a **confidence score** derived from cosine similarity and **citations** pinned to document name and page number.

---

## Features

- **Multi-format ingestion** — PDF (native text + OCR fallback for scanned), Markdown, plain text
- **Duplicate prevention** — SHA-256 hash checked before any processing
- **Scalable async ingestion** — Celery + Redis task queue for background processing; automatic fallback to in-process threads when Redis is unavailable
- **Scoped retrieval** — Queries can target a single document or search across the entire corpus
- **Conversational Q&A** — Last 3 Q&A turns rewrite follow-up questions into standalone queries
- **Confidence gating** — Answers with cosine similarity below 0.2 are rejected as "not found"
- **Document summarization** — Context-window-limited summarization (top 15 chunks) for any indexed document
- **Document management** — List and hard-delete documents (cascades to chunks and storage)
- **Containerized** — Full Docker Compose setup with backend, frontend, Redis, and Celery worker

---

## Tech Stack

| Layer | Technology | Detail |
|---|---|---|
| **API** | FastAPI | REST API, async file uploads, CORS middleware |
| **UI** | Streamlit | Single-file app (`frontend/app.py`) |
| **LLM** | `openai/gpt-oss-20b` via Groq | `langchain_groq.ChatGroq`, temperature=0 |
| **Embeddings** | `BAAI/bge-small-en-v1.5` | HuggingFace, normalized, ~80 MB download |
| **Vector DB** | Supabase (pgvector) | `match_embeddings` RPC for similarity search |
| **Storage** | Supabase Storage | `documents` bucket; files named `{sha256}_{filename}` |
| **Task Queue** | Celery + Redis | Background document ingestion with graceful fallback |
| **OCR** | Tesseract + pdf2image + Poppler | Fallback for PDFs with < 100 chars of native text |
| **PDF parsing** | PyPDFLoader + PyMuPDF | Native extraction, with OCR as secondary path |
| **Chunking** | LangChain `RecursiveCharacterTextSplitter` | 800 char chunks, 250 char overlap |
| **Containers** | Docker + Docker Compose | Backend, frontend, Redis, and Celery worker images |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Streamlit Frontend (port 8501)                                  │
│  Upload │ Select Document │ Summarize │ Chat Q&A                 │
└──────────────────┬───────────────────────────────────────────────┘
                   │  HTTP/REST
┌──────────────────▼───────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                     │
│                                                                  │
│  POST /upload ──► Celery task queue OR in-process thread         │
│      │               ├─ load_documents()  ← PDF/MD/TXT loaders  │
│      │               ├─ load_pdf_smart()  ← OCR fallback        │
│      │               ├─ RecursiveCharacterTextSplitter           │
│      │               ├─ embed_parallel()  ← ThreadPoolExecutor  │
│      │               └─ Supabase batch INSERT (1000/batch)       │
│                                                                  │
│  POST /query ──► qa.py (RAG pipeline)                            │
│  POST /summarize ──► qa.py (summarization)                       │
│  GET  /documents ──► list from Supabase                          │
│  DELETE /documents/{id} ──► cascade delete                       │
│  GET  /ingestion-status ──► Redis or in-memory state             │
└──────────────────┬──────────────────────┬────────────────────────┘
                   │                      │
┌──────────────────▼───────┐  ┌───────────▼────────────────────────┐
│  Redis (Upstash / local) │  │  Supabase                          │
│  Task broker & state     │  │  ├─ Storage: "documents" bucket    │
│                          │  │  ├─ Table: documents (metadata)    │
└──────────────────────────┘  │  ├─ Table: chunks (text+embedding) │
                              │  └─ RPC: match_embeddings()        │
                              └────────────────────────────────────┘
```

---

## Project Structure

```
intyrasense/
├── backend/
│   ├── main.py            # FastAPI app, endpoint definitions
│   ├── ingest.py          # Ingestion pipeline (load → chunk → embed → store)
│   ├── qa.py              # RAG Q&A + summarization
│   ├── retriever.py       # pgvector similarity search, query embedding cache
│   ├── models.py          # LLM (ChatGroq) + embeddings (HuggingFace) singletons
│   ├── prompts.py         # SYSTEM_PROMPT (Q&A) + SUMMARY_PROMPT
│   ├── supabase_client.py # Singleton Supabase client with env validation
│   ├── celery_app.py      # Celery app config, Redis broker, availability probe
│   ├── tasks.py           # Celery task: ingest_documents_task
│   ├── state.py           # Ingestion status (Redis-backed + in-memory fallback)
│   ├── utils.py           # file_hash(), list_documents(), get_doc_id_from_name()
│   └── requirements.txt
├── frontend/
│   ├── app.py             # Streamlit UI: upload, select, summarize, chat
│   └── requirements.txt
├── Docker/
│   ├── docker-compose.yml     # Backend + frontend + Redis + Celery worker
│   ├── Dockerfile.backend     # Python 3.11 + Tesseract + Poppler
│   └── Dockerfile.frontend    # Python 3.11 slim
├── docs/
│   ├── PROJECT_STATE.md
│   ├── DEVELOPMENT_CONTEXT.md
│   ├── CHANGELOG.md
│   ├── ARCHITECTURE.md
│   ├── SETUP.md
│   └── DEPLOYMENT.md
├── .env.example
├── Makefile
└── requirements.txt           # Root-level unified deps
```

---

## Installation & Setup

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Tested on 3.11, 3.12, 3.13 |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |
| Supabase project | Requires `documents` + `chunks` tables and `match_embeddings` RPC |
| Redis | Upstash (cloud) or local — optional, graceful fallback without it |
| Tesseract + Poppler | Optional — only needed for scanned PDF support |

### 1. Clone & configure

```bash
git clone https://github.com/<your-username>/intyrasense.git
cd intyrasense

cp .env.example .env
# Edit .env and fill in:
#   GROQ_API_KEY=gsk_...
#   SUPABASE_URL=https://your-project-ref.supabase.co
#   SUPABASE_KEY=your_supabase_anon_or_service_key
#   REDIS_URL=rediss://default:...@....upstash.io:6379  (or redis://localhost:6379/0)
```

### 2. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** First run downloads `BAAI/bge-small-en-v1.5` (~80 MB). Cached on subsequent runs.

### 3. Start the application

**Terminal 1 — Backend:**

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend:**

```bash
streamlit run frontend/app.py
```

**Terminal 3 — Celery Worker (optional):**

```bash
celery -A backend.celery_app.celery worker --loglevel=info -P solo
```

> Without the Celery worker, ingestion runs via in-process threads. With it, tasks are distributed through Redis.

### 4. Install OCR dependencies (optional)

For scanned PDF support:

- **Ubuntu/Debian:** `sudo apt-get install -y tesseract-ocr poppler-utils`
- **macOS:** `brew install tesseract poppler`
- **Windows:** Download [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and [Poppler](https://github.com/oschwartz10612/poppler-windows/releases)

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLM inference |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_KEY` | Yes | — | Supabase API key (anon or service) |
| `BACKEND_URL` | No | `http://localhost:8000` | Backend URL for the frontend to connect to |
| `USE_CELERY` | No | `true` | Enable Celery task queue for ingestion |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL (supports `rediss://` for TLS) |
| `CELERY_BROKER_URL` | No | Value of `REDIS_URL` | Override Celery broker URL separately |
| `CELERY_RESULT_BACKEND` | No | Value of `REDIS_URL` | Override Celery result backend URL separately |

---

## Database Schema (Supabase)

### `documents` table

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated document identifier |
| `name` | text | Original filename (stripped of hash prefix) |
| `storage_path` | text | Full path in Supabase Storage: `{sha256}_{filename}` |
| `type` | text | File extension: `pdf`, `md`, `txt` |
| `file_hash` | text | SHA-256 of raw file bytes — used for deduplication |

### `chunks` table

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Auto-generated chunk identifier |
| `source` | UUID (FK → `documents.id`) | Parent document reference |
| `page` | integer | Page number from source document |
| `text` | text | Raw chunk content (800 char segments) |
| `embedding` | vector | BAAI/bge-small-en-v1.5 output (normalized) |

### Supabase RPC: `match_embeddings`

Called by `retriever.py` with parameters:
- `query_embedding` — float array from the query encoder
- `match_count` — top-k results (default: 10)
- `filter_source` _(optional)_ — UUID to scope search to one document

Returns: `text`, `source`, `page`, `score` (cosine similarity)

---

## API Endpoints

| Method | Endpoint | Request | Response |
|---|---|---|---|
| `GET` | `/` | — | `{ status: "running" }` |
| `HEAD` | `/` | — | 200 OK |
| `POST` | `/upload` | `multipart/form-data` (files) | `{ status, files[], message, task_id? }` |
| `GET` | `/ingestion-status` | `?task_id=...` (optional) | `{ state: "idle" \| "running" \| "completed" \| "failed", task_id? }` |
| `POST` | `/query` | `{ question, chat_history, document? }` | `{ answer, citations[], confidence }` |
| `POST` | `/summarize` | `{ document? }` | `{ summary, citations[] }` |
| `GET` | `/documents` | — | `{ documents: [{ id, name, storage_path }] }` |
| `DELETE` | `/documents/{doc_id}` | path param | `{ status: "deleted", doc_id }` |

Swagger/OpenAPI docs available at `http://localhost:8000/docs`.

---

## Docker Deployment

```bash
# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start all services (Redis, Celery worker, backend, frontend)
docker compose -f Docker/docker-compose.yml up --build
```

| Service | Port | Description |
|---------|------|-------------|
| `redis` | 6379 | Redis 7 Alpine with healthcheck |
| `celery_worker` | — | Background task processor |
| `backend` | 8000 | FastAPI API server |
| `frontend` | 8501 | Streamlit web UI |

```bash
# Stop services
docker compose -f Docker/docker-compose.yml down
```

---

## Makefile Targets

```bash
make install    # Install all Python dependencies
make backend    # Start FastAPI backend
make frontend   # Start Streamlit frontend
make worker     # Start Celery worker (Windows: -P solo)
make docker-up  # Docker Compose up --build
make docker-down # Docker Compose down
make clean      # Remove __pycache__ and .pyc files
```

---

## License

[MIT](LICENSE)