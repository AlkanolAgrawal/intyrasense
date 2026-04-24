<div align="center">

# INTYRASENSE

**Document-grounded Q&A and summarization over unstructured data.**  
Upload PDFs, Markdown, or text files — ask questions, get sourced answers.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## Overview

INTYRASENSE is a **Retrieval-Augmented Generation (RAG)** system that lets users upload internal documents and query them through a conversational interface. It enforces strict source grounding — the LLM only answers from retrieved context, never from its training data. Each answer includes a **confidence score** derived from vector similarity and **citations** pinned to document name and page number.

The system handles scanned PDFs via an OCR fallback, deduplicates uploads by SHA-256 content hash, and runs embedding generation asynchronously so the API stays non-blocking during ingestion.

---

## Features

- **Multi-format ingestion** — PDF (native text + OCR fallback for scanned), Markdown, plain text
- **Duplicate prevention** — SHA-256 hash checked against `documents` table before any processing
- **Asynchronous ingestion** — embedding pipeline runs in a background thread; clients poll `/ingestion-status`
- **Scoped retrieval** — queries can target a single document or search across the entire corpus
- **Conversational Q&A** — last 3 Q&A turns are used to rewrite follow-up questions into standalone queries
- **Confidence gating** — answers with cosine similarity below 0.2 are rejected as "not found"
- **Document summarization** — context-window-limited summarization (top 15 chunks) for any indexed document
- **Document management** — list and hard-delete documents (cascades to chunks and storage)
- **Containerized** — full Docker Compose setup with backend and frontend as isolated services

---

## Tech Stack

| Layer | Technology | Detail |
|---|---|---|
| **API** | FastAPI | REST API, async file uploads, CORS middleware |
| **UI** | Streamlit | Single-file app (`frontend/app.py`) |
| **LLM** | LLaMA 3.1 8B via Groq | `langchain_groq.ChatGroq`, temperature=0 |
| **Embeddings** | `BAAI/bge-small-en-v1.5` | HuggingFace, normalized, ~80 MB download |
| **Vector DB** | Supabase (pgvector) | `match_embeddings` RPC for similarity search |
| **Storage** | Supabase Storage | `documents` bucket; files named `{sha256}_{filename}` |
| **OCR** | Tesseract + pdf2image + Poppler | Fallback for PDFs with < 100 chars of native text |
| **PDF parsing** | PyPDFLoader + PyMuPDF | Native extraction, with OCR as secondary path |
| **Chunking** | LangChain `RecursiveCharacterTextSplitter` | 800 char chunks, 250 char overlap |
| **Orchestration** | LangChain Core | Prompt templates, message types |
| **Containers** | Docker + Docker Compose | Separate backend/frontend images, shared network |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Streamlit Frontend (port 8501)                                  │
│  Upload │ Select Document │ Summarize │ Chat Q&A                 │
└──────────────────┬───────────────────────────────────────────────┘
                   │  HTTP/REST (requests)
┌──────────────────▼───────────────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                     │
│                                                                  │
│  POST /upload ──► ingest.py (background thread)                  │
│      │               ├─ load_documents()  ← PDF/MD/TXT loaders   │
│      │               ├─ load_pdf_smart()  ← OCR fallback         │
│      │               ├─ RecursiveCharacterTextSplitter            │
│      │               ├─ embed_parallel()  ← ThreadPoolExecutor   │
│      │               └─ Supabase batch INSERT (chunks, 1000/batch)│
│                                                                  │
│  POST /query ──► qa.py                                           │
│      │               ├─ rewrite_question()  ← chat-aware rewrite │
│      │               ├─ retrieve_with_score() ← pgvector RPC     │
│      │               ├─ confidence = max(cosine_scores)           │
│      │               └─ llm().invoke(SYSTEM_PROMPT)               │
│                                                                  │
│  POST /summarize ──► qa.py                                       │
│      │               └─ top 15 chunks → llm().invoke(SUMMARY_...) │
│                                                                  │
│  GET  /documents      ──► utils.list_documents()                 │
│  DELETE /documents/{id} ──► cascade: chunks → storage → record  │
│  GET  /ingestion-status ──► state.py (in-memory dict)            │
└──────────────────┬───────────────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────────────┐
│  Supabase                                                        │
│  ├─ Storage bucket: "documents"  (raw uploaded files)            │
│  ├─ Table: documents             (metadata + file_hash)          │
│  ├─ Table: chunks                (text + pgvector embeddings)    │
│  └─ RPC:   match_embeddings()    (cosine similarity search)      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Model

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

## Pipelines

### Ingestion Pipeline

```
POST /upload (multipart)
  → SHA-256 hash per file
  → Skip if hash already in `documents` table
  → Upload raw bytes to Supabase Storage as "{hash}_{filename}"
  → Insert record into `documents`
  → background thread: ingest_documents(uploaded_files)
      → Download from Storage → write to temp file
      → PDF: PyPDFLoader → if text < 100 chars: Tesseract OCR via pdf2image
      → MD: UnstructuredMarkdownLoader
      → TXT: TextLoader
      → RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=250)
      → Filter chunks < 20 chars
      → embed_parallel(): ThreadPoolExecutor(4 workers), batch_size=64
      → Batch INSERT into `chunks` (1000 records/batch)
      → set_ingestion_status("completed" | "failed")
```

### Query Pipeline

```
POST /query { question, chat_history, document }
  → rewrite_question(): if chat_history, use last 3 pairs to rewrite to standalone
  → get_doc_id_from_name(document) → resolve storage_path → doc UUID
  → retrieve_with_score(query, doc_id, k=10)
      → embed_query_cached(): lru_cache(256) on normalized query embedding
      → supabase.rpc("match_embeddings", params)
  → Slice top 5 results
  → confidence = max(similarity_scores), clamped to [0.0, 1.0]
  → If confidence < 0.2: return "Not found in internal documents."
  → Build context from chunk texts
  → llm().invoke(SYSTEM_PROMPT.format(context, question))
  → Return { answer, citations: ["filename — page N"], confidence }
```

---

## API Endpoints

| Method | Endpoint | Request | Response |
|---|---|---|---|
| `GET` | `/` | — | `{ status: "running" }` |
| `POST` | `/upload` | `multipart/form-data` (files) | `{ status, files[], message }` |
| `GET` | `/ingestion-status` | — | `{ state: "idle" \| "running" \| "completed" \| "failed" }` |
| `POST` | `/query` | `{ question, chat_history, document? }` | `{ answer, citations[], confidence }` |
| `POST` | `/summarize` | `{ document? }` | `{ summary, citations[] }` |
| `GET` | `/documents` | — | `{ documents: [{ id, name, storage_path }] }` |
| `DELETE` | `/documents/{doc_id}` | path param | `{ status: "deleted", doc_id }` |

Swagger/OpenAPI docs available at `http://localhost:8000/docs`.

---

## Project Structure

```
intyrasense/
├── backend/
│   ├── main.py            # FastAPI app, endpoint definitions
│   ├── ingest.py          # Full ingestion pipeline (load → chunk → embed → store)
│   ├── qa.py              # RAG orchestration: Q&A + summarization
│   ├── retriever.py       # pgvector similarity search, query embedding cache
│   ├── models.py          # LLM (ChatGroq) + embeddings (HuggingFace) singletons
│   ├── prompts.py         # SYSTEM_PROMPT (Q&A) + SUMMARY_PROMPT
│   ├── supabase_client.py # Singleton Supabase client with env validation
│   ├── state.py           # In-memory ingestion status tracker
│   ├── utils.py           # file_hash(), list_documents(), get_doc_id_from_name()
│   └── requirements.txt
├── frontend/
│   ├── app.py             # Streamlit UI: upload, select, summarize, chat
│   └── requirements.txt
├── Docker/
│   ├── docker-compose.yml     # Backend + frontend services, shared bridge network
│   ├── Dockerfile.backend     # Python 3.11 + Tesseract + Poppler
│   └── Dockerfile.frontend    # Python 3.11 slim
├── docs/
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
| Python 3.11+ | Tested on 3.11 and 3.12 |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |
| Supabase project | Requires `documents` + `chunks` tables and `match_embeddings` RPC |
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
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** First run downloads `BAAI/bge-small-en-v1.5` (~80 MB). Cached on subsequent runs.

### 3. Install OCR dependencies (optional, for scanned PDFs)

```bash
# Ubuntu / Debian
sudo apt-get install -y tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler
```

### 4. Run

**Terminal 1 — Backend:**

```bash
uvicorn backend.main:app --reload
# API: http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

**Terminal 2 — Frontend:**

```bash
streamlit run frontend/app.py
# UI: http://localhost:8501
```

Or use Makefile shortcuts:

```bash
make install     # Install all dependencies
make backend     # Start FastAPI backend
make frontend    # Start Streamlit frontend
make docker-up   # Start both with Docker Compose
make clean       # Remove __pycache__ and .pyc files
```

### Docker (alternative)

```bash
# Ensure .env is populated
make docker-up
# Backend: http://localhost:8000
# Frontend: http://localhost:8501
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLaMA inference |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_KEY` | Yes | — | Supabase anon or service role key |
| `BACKEND_URL` | No | `http://localhost:8000` | Backend URL used by Streamlit |

---

## Usage

1. **Upload documents** — Drag and drop PDF, Markdown, or text files (up to 50 MB each). Click **Upload & Index**. A status indicator polls `/ingestion-status` until ingestion completes.
2. **Select scope** — Choose a specific document or leave on *All Documents* to search across the full corpus.
3. **Summarize** — Click **Summarize Document** to get a structured summary of the selected document.
4. **Ask questions** — Type in the chat input. Answers include a **confidence score** and **expandable citations** showing source document and page.
5. **Delete documents** — Click the 🗑 button next to any document to remove it from the index and storage.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| **Supabase + pgvector** | Managed Postgres with first-class vector support; eliminates a separate vector DB dependency |
| **BAAI/bge-small-en-v1.5** | Strong retrieval quality at low latency (~33M params); normalized embeddings work directly with cosine similarity |
| **Groq (LLaMA 3.1 8B)** | Sub-second inference; deterministic at temperature=0; free tier sufficient for development |
| **SHA-256 deduplication** | Content-addressed storage prevents re-ingestion of identical files regardless of filename |
| **Background threading** | Keeps `/upload` non-blocking; avoids HTTP timeout on large document sets |
| **LRU cache on embeddings** | Query embeddings are cached (256 entries) to avoid redundant model calls for repeated questions |
| **Confidence threshold (0.2)** | Hard floor on cosine similarity; prevents the LLM from generating confabulated answers on low-signal retrieval |
| **Chunk size 800 / overlap 250** | Balances context richness per chunk with retrieval precision; overlap preserves sentence continuity at boundaries |

---

## Limitations

- **In-memory ingestion state** — `state.py` uses a plain dict. Status is lost on server restart; concurrent uploads overwrite each other's state.
- **No authentication** — All endpoints are open. CORS is set to `allow_origins=["*"]`.
- **Summarization context cap** — Summarization fetches only the first 15 chunks from the DB, not the full document.
- **Single-worker embedding** — While `embed_parallel` uses a thread pool, the HuggingFace model is a shared singleton; true parallelism is limited by the GIL.
- **No re-indexing** — Updating a document requires deleting and re-uploading; there is no partial update path.
- **LLM context window** — Very large retrieved contexts are not truncated before being passed to the LLM.

---

## Future Improvements

- [ ] Replace in-memory ingestion state with a persistent job queue (Celery + Redis or Supabase queue)
- [ ] Add JWT-based authentication and per-user document namespacing
- [ ] Expose a streaming `/query/stream` endpoint using Server-Sent Events
- [ ] Add re-ranking step (cross-encoder) between retrieval and generation to improve answer quality
- [ ] Support `.docx` and `.pptx` via additional LangChain loaders
- [ ] Migrate frontend to React + Vite for production-grade UI scalability
- [ ] Implement document versioning — re-ingest changed files without full delete/reupload

---

## License
MIT © [ Rohan Agrawal ](https://github.com/AlkanolAgrawal)