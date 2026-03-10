<div align="center">

# 🧠 INTYRASENSE

**Document-Grounded Question Answering & Summarization powered by RAG**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<p align="center">
  <em>A strict Retrieval-Augmented Generation system that answers questions <strong>only</strong> from your uploaded documents — no hallucination, no external knowledge.</em>
</p>

</div>

---

## 📸 Demo

> **Screenshots coming soon** — contributions welcome!

<!-- Uncomment when screenshots are available:
<div align="center">
  <img src="docs/assets/screenshot-upload.png" alt="Upload Interface" width="45%">
  <img src="docs/assets/screenshot-chat.png" alt="Chat Interface" width="45%">
</div>
-->

---

## 🏗️ Architecture

```text
┌──────────────┐        HTTP         ┌──────────────────────────────┐
│   Streamlit  │ ◄──────────────────►│         FastAPI Backend      │
│   Frontend   │    REST API calls   │                              │
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

> For a detailed architecture breakdown, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📄 **Multi-Format Upload** | Supports PDF, Markdown, and plain text files |
| 🔍 **Semantic Search** | FAISS + sentence-transformers for fast vector similarity |
| 💬 **Context-Aware Q&A** | Rewrites follow-up questions using chat history |
| 📝 **Document Summarization** | Hierarchical summarization for large documents |
| 🎯 **Confidence Scoring** | Every answer includes a retrieval confidence score |
| 📌 **Source Citations** | References source files and page numbers |
| 🔒 **Strict RAG** | Never halluccinates — says "not found" when unsure |
| 🔄 **Document Filtering** | Query a single document or search across all |
| 🖼️ **OCR Fallback** | Extracts text from scanned PDFs via Tesseract |

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com) |
| **Frontend** | [Streamlit](https://streamlit.io) |
| **RAG Framework** | [LangChain](https://langchain.com) |
| **Vector Store** | [FAISS](https://github.com/facebookresearch/faiss) (Facebook AI Similarity Search) |
| **Embeddings** | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) via HuggingFace |
| **LLM** | [Groq](https://groq.com) — Llama 3.1 8B Instant |
| **PDF Parsing** | PyPDF + Tesseract OCR fallback |
| **Containerization** | Docker & Docker Compose |

---

## 📁 Project Structure

```text
intyrasense/
├── backend/
│   ├── __init__.py
│   ├── main.py             # FastAPI app — upload, query, summarize endpoints
│   ├── ingest.py           # Document loading, chunking, FAISS index creation
│   ├── qa.py               # Question answering & summarization logic
│   ├── retriever.py        # Vector store retrieval with filtering
│   ├── prompts.py          # System prompts for Q&A and summarization
│   ├── utils.py            # Helper functions (document listing)
│   └── requirements.txt    # Backend Python dependencies
├── frontend/
│   ├── app.py              # Streamlit web interface
│   └── requirements.txt    # Frontend Python dependencies
├── data/
│   ├── raw_docs/           # Uploaded source documents
│   └── faiss_index/        # Generated FAISS vector index
├── Docker/
│   ├── docker-compose.yml  # Multi-container orchestration
│   ├── Dockerfile.backend  # Backend container image
│   └── Dockerfile.frontend # Frontend container image
├── docs/
│   ├── ARCHITECTURE.md     # Detailed architecture documentation
│   ├── SETUP.md            # Step-by-step setup guide
│   └── DEPLOYMENT.md       # Deployment instructions
├── .env.example            # Environment variable template
├── .gitignore
├── Makefile                # Developer shortcuts
├── LICENSE
├── requirements.txt        # Root-level dependencies
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Groq API key** — [get one free](https://console.groq.com)
- **Tesseract OCR** *(optional, for scanned PDFs)*
- **Docker & Docker Compose** *(optional, for containerized setup)*

### Option 1: Local Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/intyrasense.git
cd intyrasense

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

**Start the application:**

```bash
# Terminal 1 — Backend
uvicorn backend.main:app --reload

# Terminal 2 — Frontend
streamlit run frontend/app.py
```

| Service | URL |
|---------|-----|
| Backend API | http://127.0.0.1:8000 |
| API Docs (Swagger) | http://127.0.0.1:8000/docs |
| Frontend | http://localhost:8501 |

### Option 2: Docker

```bash
# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# Build and start all services
docker compose -f Docker/docker-compose.yml up --build
```

> See [docs/SETUP.md](docs/SETUP.md) for detailed installation instructions and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment.

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | API key for Groq LLM inference |
| `BACKEND_URL` | No | `http://127.0.0.1:8000` | Backend URL (used by frontend) |

Create a `.env` file from the template:

```bash
cp .env.example .env
```

---

## 📡 API Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|-------------|
| `POST` | `/upload` | Upload & index documents | `multipart/form-data` — `files` |
| `POST` | `/query` | Ask a question | `{"question": "...", "chat_history": [], "document": null}` |
| `POST` | `/summarize` | Summarize a document | `{"document": "filename.pdf"}` |
| `GET` | `/documents` | List indexed documents | — |

### Example: Query

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic?", "chat_history": [], "document": null}'
```

**Response:**

```json
{
  "answer": "The main topic is ...",
  "citations": ["document.pdf | page 3"],
  "confidence": 0.87
}
```

### Example: Upload

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -F "files=@path/to/document.pdf"
```

### Example: Summarize

```bash
curl -X POST http://127.0.0.1:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"document": "document.pdf"}'
```

---

## 🧑‍💻 Usage

1. **Upload Documents** — Use the sidebar to upload PDF, Markdown, or text files. Click **"Upload & Index"** to process them.
2. **Select Scope** — Choose a specific document or search across all uploads.
3. **Ask Questions** — Type fact-based questions in the chat. The system retrieves relevant chunks, scores confidence, and cites sources.
4. **Summarize** — Select a document and click **"Summarize Document"** for a concise overview.

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-feature`
3. **Commit** your changes: `git commit -m "feat: add my feature"`
4. **Push** to the branch: `git push origin feature/my-feature`
5. **Open** a Pull Request

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Alkanol** — [GitHub](https://github.com/alkanol)

---

<div align="center">
  <sub>Built with ❤️ using LangChain, FastAPI, and Streamlit</sub>
</div>
