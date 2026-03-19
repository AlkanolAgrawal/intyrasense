<div align="center">

# INTYRASENSE

**Production-grade document intelligence system (RAG)**  
Grounded Q&A + summarization over unstructured data.

Built with FastAPI, Streamlit, LangChain, and Supabase.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## 🚀 Overview

INTYRASENSE is a **retrieval-augmented generation (RAG) system** for document-grounded question answering and summarization.


## 📄 Document Processing Pipeline

```
Ingest → Parse → Chunk → Embed → Retrieve → Generate
```

### 1. Ingest

* Accept documents (PDF, TXT, MD, etc.)
* Store raw files
* Compute hash for deduplication

### 2. Parse

* Extract text from documents
* OCR applied for scanned PDFs
* Normalize content into structured format

### 3. Chunk

* Split text into smaller segments
* Maintain overlap for context preservation
* Attach metadata (source, page, etc.)

### 4. Embed

* Convert chunks into vector embeddings
* Store in vector database (e.g., Supabase / pgvector)

### 5. Retrieve

* Perform similarity search using query embeddings
* Return top-K relevant chunks with scores

### 6. Generate

* Feed retrieved context into LLM
* Generate grounded response with citations

---

**Core guarantees**
- Source-grounded answers (no blind LLM output)
- Deterministic ingestion (idempotent uploads)
- Confidence scoring from retrieval similarity

---

## 🏗 System Architecture

```text
[ Streamlit UI ]
        |
        v
[ FastAPI Backend ]
        |
        |---- Ingestion Pipeline (async)
        |       - SHA-256 deduplication
        |       - Parsing (PDF/MD/TXT)
        |       - OCR fallback (low-text PDFs)
        |       - Chunking (overlap tuned)
        |       - Embedding generation
        |
        |---- Query Pipeline
        |       - Query rewriting (chat-aware)
        |       - Vector search (Supabase RPC)
        |       - Context assembly
        |       - LLM inference
        |       - Confidence scoring
        |
        v
[ Supabase ]
  - Storage (documents)
  - Tables (documents, chunks)
  - pgvector + match_embeddings RPC

```
| Layer      | Choice                | Reason                     |
| ---------- | --------------------- | -------------------------- |
| API        | FastAPI               | Async, high-performance    |
| UI         | Streamlit             | Rapid iteration            |
| Vector DB  | Supabase (pgvector)   | SQL-native, scalable       |
| Embeddings | BGE-small-en-v1.5     | Quality vs latency balance |
| LLM        | LLaMA 3.1 (Groq)      | Low-latency inference      |
| OCR        | Tesseract + pdf2image | Handles scanned documents  |

## Project Structure
intyrasense/
├── backend/
│   ├── ingest.py        # ingestion pipeline
│   ├── retriever.py     # vector search abstraction
│   ├── qa.py            # RAG orchestration
│   ├── models.py        # embeddings + LLM config
│   ├── prompts.py       # prompt templates
│   ├── utils.py         # hashing + helpers
│   └── main.py          # API entrypoint
├── frontend/
│   └── app.py           # UI
├── Docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── docs/
├── .env.example
├── Makefile
└── README.md

```
## API Endpoints

| Endpoint            | Purpose                |
| ------------------- | ---------------------- |
| `/upload`           | Trigger ingestion      |
| `/query`            | Execute RAG pipeline   |
| `/summarize`        | Document summarization |
| `/documents`        | List documents         |
| `/ingestion-status` | Track async ingestion  |

```
## Local Development
make install
make run-backend
make run-frontend
### OR Dockerized:
make docker-up
```
| Variable       | Required | Description          |
| -------------- | -------- | -------------------- |
| `GROQ_API_KEY` | Yes      | LLM API key          |
| `SUPABASE_URL` | Yes      | Supabase project URL |
| `SUPABASE_KEY` | Yes      | Supabase API key     |
| `BACKEND_URL`  | No       | Frontend backend URL |
