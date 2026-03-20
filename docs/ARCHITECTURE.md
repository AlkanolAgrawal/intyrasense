# 🏗️ Architecture

> Detailed architecture documentation for INTYRASENSE.

---

## Overview

INTYRASENSE is a **Retrieval-Augmented Generation (RAG)** system with a strict no-hallucination policy. It uses a two-service architecture: a **FastAPI backend** for document processing & LLM orchestration, and a **Streamlit frontend** for the user interface.

```text
┌──────────────┐        HTTP/REST    ┌──────────────────────────────┐
│   Streamlit  │ ◄──────────────────►│         FastAPI Backend      │
│   Frontend   │                     │                              │
│  (port 8501) │                     │  ┌────────┐  ┌──────────┐   │
└──────────────┘                     │  │ Ingest │  │Retriever │   │
                                     │  │Pipeline│  │(pgvector)    │
                                     │  └───┬────┘  └─────┬────┘   │
                                     │      │             │        │
                                     │  ┌───▼─────────────▼─────┐  │
                                     │  │   QA / Summarization  │  │
                                     │  │   (LangChain + Groq)  │  │
                                     │  └───────────────────────┘  │
                                     └──────────────┬──────────────┘
                                                    │
                                     ┌──────────────▼──────────────┐
                                     │     Supabase Backend        │
                                     │  📄 Storage (uploads)       │
                                     │  🗂️  Tables + pgvector      │
                                     └─────────────────────────────┘
```

---

## Components

### 1. Frontend — Streamlit (`frontend/app.py`)

The frontend provides an interactive web UI with four main sections:

| Section | Functionality |
|---------|--------------|
| **Upload** | File upload widget accepting PDF, Markdown, and text files |
| **Document Selection** | Dropdown to scope queries to a specific document or all |
| **Summarization** | One-click summary generation for selected documents |
| **Chat (Q&A)** | Conversational interface with chat history, confidence scores, and citations |

Communication with the backend is done via `requests` HTTP calls to the FastAPI REST API.

### 2. Backend — FastAPI (`backend/`)

#### `main.py` — API Layer

Defines four endpoints:

- `POST /upload` — Receives files, saves to disk, triggers ingestion pipeline
- `POST /query` — Accepts a question + chat history, returns answer with citations
- `POST /summarize` — Summarizes a selected document
- `GET /documents` — Lists all indexed documents

#### `ingest.py` — Document Ingestion Pipeline

```text
Upload → Load (PDF/MD/TXT) → OCR Fallback → Chunk (800 chars, 250 overlap) → Embed → Supabase pgvector
```

Key behaviors:
- **Smart PDF loading**: Tries native text extraction first, falls back to Tesseract OCR for scanned documents
- **Recursive chunking**: Uses `RecursiveCharacterTextSplitter` for semantically coherent chunks
- **Full rebuild**: Each ingestion clears and rebuilds the entire FAISS index

#### `retriever.py` — Vector Retrieval

- Queries Supabase `match_embeddings()` RPC function for similarity search
- Embedding model (`BAAI/bge-small-en-v1.5`) loaded at module level (singleton pattern via `@lru_cache`)
- Supports filtered retrieval (by document source) or global search
- Returns documents with similarity scores for confidence calculation

#### `qa.py` — Question Answering & Summarization

**Q&A Pipeline:**

1. **Question rewriting** — Rewrites follow-up questions into standalone queries using last 3 Q&A pairs
2. **Retrieval** — Fetches top-k relevant chunks with similarity scores
3. **Confidence scoring** — `confidence = 1 / (1 + avg_distance)`, rejects below 0.25
4. **Answer generation** — LLM generates answer using strict system prompt
5. **Citation extraction** — Extracts source file + page from chunk metadata

**Summarization Pipeline:**

- **Small documents** (< 6000 chars): Direct single-pass summarization
- **Large documents**: Hierarchical — summarize each chunk, then summarize the summaries

#### `prompts.py` — System Prompts

Contains two prompt templates:
- `SYSTEM_PROMPT` — Strict Q&A prompt that forbids external knowledge and hallucination
- `SUMMARY_PROMPT` — Summarization prompt that covers main topic, key ideas, and conclusions

#### `utils.py` — Utilities

Simple helper to list available documents from the raw documents directory.

### 3. Data Layer (Supabase)

| Table | Purpose |
|-------|----------|
| `documents` | Metadata: file_hash, storage_path, name, type |
| `chunks` | Full-text chunks with embeddings (pgvector) |
| `storage.documents` | Bucket for uploaded files (PDF, MD, TXT) |

### 4. Containerization (`Docker/`)

- **`docker-compose.yml`** — Orchestrates backend + frontend services with shared data volume
- **`Dockerfile.backend`** — Python 3.11 slim + Tesseract + Poppler for OCR support
- **`Dockerfile.frontend`** — Python 3.11 slim with pip cache mount for fast rebuilds

---

## Data Flow

### Document Upload Flow

```text
User uploads file(s) via Streamlit
  → POST /upload (multipart/form-data)
    → Upload to Supabase Storage
    → ingest_documents() (background thread)
      → load_documents() — PDF/MD/TXT loaders + OCR fallback
      → RecursiveCharacterTextSplitter (800 chars, 250 overlap)
      → Embed chunks with HuggingFace model
      → Batch insert into Supabase `chunks` table with embeddings
    → Return success message
```

### Question Answering Flow

```text
User types question in chat
  → POST /query { question, chat_history, document }
    → rewrite_question() — standalone query from follow-up
    → retrieve_with_score() — Supabase pgvector similarity search (k=10 or k=50 filtered)
    → Calculate confidence from similarity scores
    → If confidence < 0.2: reject as "Not found"
    → Build context from retrieved chunks
    → LLM generates answer with SYSTEM_PROMPT
    → Return { answer, citations, confidence }
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Supabase + pgvector** | Managed PostgreSQL with vector extension; scalable, redundant, SQL-native |
| **BGE-small-en-v1.5** | High-quality embeddings with reasonable inference latency |
| **Groq API** | Extremely fast inference for Llama models; free tier available |
| **Batch insertion** | Efficient document ingestion; deduplication via file_hash |
| **Strict system prompt** | Core requirement — prevents hallucination and ensures source grounding |
| **Confidence threshold (0.2)** | Prevents low-quality answers from reaching the user |
