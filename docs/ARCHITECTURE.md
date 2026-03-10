# 🏗️ Architecture

> Detailed architecture documentation for INTYRASENSE.

---

## Overview

INTYRASENSE is a **Retrieval-Augmented Generation (RAG)** system with a strict no-hallucination policy. It uses a two-service architecture: a **FastAPI backend** for document processing & LLM orchestration, and a **Streamlit frontend** for the user interface.

```text
┌──────────────┐        HTTP/REST    ┌──────────────────────────────┐
│   Streamlit  │ ◄──────────────────►│         FastAPI Backend      │
│   Frontend   │                     │                              │
│  (port 8501) │                     │  ┌────────┐  ┌───────────┐  │
└──────────────┘                     │  │ Ingest │  │ Retriever │  │
                                     │  │Pipeline│  │  (FAISS)  │  │
                                     │  └───┬────┘  └─────┬─────┘  │
                                     │      │             │        │
                                     │  ┌───▼─────────────▼─────┐  │
                                     │  │   QA / Summarization  │  │
                                     │  │   (LangChain + Groq)  │  │
                                     │  └───────────────────────┘  │
                                     └──────────────┬──────────────┘
                                                    │
                                     ┌──────────────▼──────────────┐
                                     │       Data Layer            │
                                     │  📄 raw_docs/  (uploads)   │
                                     │  🗂️  faiss_index/ (vectors) │
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
Upload → Load (PDF/MD/TXT) → OCR Fallback → Chunk (2000 chars, 250 overlap) → Embed → FAISS Index
```

Key behaviors:
- **Smart PDF loading**: Tries native text extraction first, falls back to Tesseract OCR for scanned documents
- **Recursive chunking**: Uses `RecursiveCharacterTextSplitter` for semantically coherent chunks
- **Full rebuild**: Each ingestion clears and rebuilds the entire FAISS index

#### `retriever.py` — Vector Retrieval

- Loads a shared FAISS index and embedding model at module level (singleton pattern)
- Supports filtered retrieval (by document source) or global search
- Returns documents with similarity scores for confidence calculation
- Provides `reload_index()` to refresh after new ingestion

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

### 3. Data Layer (`data/`)

| Directory | Contents |
|-----------|----------|
| `data/raw_docs/` | Uploaded source documents (PDF, MD, TXT) |
| `data/faiss_index/` | Serialized FAISS vector index (`index.faiss` + `index.pkl`) |

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
    → Save files to data/raw_docs/
    → ingest_documents()
      → load_documents() — PDF/MD/TXT loaders + OCR fallback
      → RecursiveCharacterTextSplitter (2000 chars, 250 overlap)
      → FAISS.from_documents() — embed + index
      → Save to data/faiss_index/
    → Return success
```

### Question Answering Flow

```text
User types question in chat
  → POST /query { question, chat_history, document }
    → rewrite_question() — standalone query from follow-up
    → retrieve_with_score() — FAISS similarity search (k=10 or k=50 filtered)
    → Calculate confidence: 1 / (1 + avg_distance)
    → If confidence < 0.25: reject
    → Build context from retrieved chunks
    → LLM generates answer with SYSTEM_PROMPT
    → Return { answer, citations, confidence }
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **FAISS over Chroma/Pinecone** | Zero external dependencies, fast CPU-based similarity search |
| **Full index rebuild** | Simpler than incremental updates; acceptable for the expected document volume |
| **Groq API** | Extremely fast inference for Llama models; free tier available |
| **all-MiniLM-L6-v2** | Good balance of quality and speed; runs on CPU |
| **Strict system prompt** | Core requirement — prevents hallucination and ensures source grounding |
| **Confidence threshold (0.25)** | Prevents low-quality answers from reaching the user |
