# 🛠️ Setup Guide

> Step-by-step instructions to get INTYRASENSE running locally.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Tested with 3.11 and 3.12 |
| pip | Latest | `pip install --upgrade pip` |
| Groq API Key | — | [Get one free](https://console.groq.com) |
| Supabase project | — | [Create one](https://supabase.com) with `documents` + `chunks` tables |
| Redis | Optional | Upstash (cloud) or local — graceful fallback without it |
| Tesseract OCR | Optional | Required only for scanned PDF support |
| Poppler | Optional | Required only for PDF-to-image conversion (OCR) |
| Docker | Optional | For containerized deployment |

---

## 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/intyrasense.git
cd intyrasense
```

---

## 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS
```

---

## 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note**: The first run will download the `BAAI/bge-small-en-v1.5` embedding model (~80 MB). This is a one-time download.

---

## 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and set your credentials:

```env
# Required
GROQ_API_KEY=gsk_your_actual_key_here
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_supabase_key_here

# Optional — Celery + Redis
USE_CELERY=true
REDIS_URL=redis://localhost:6379/0
# For Upstash: REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379
```

See `.env.example` for the full list of variables.

---

## 5. Install System Dependencies (Optional — OCR Support)

For processing scanned PDFs, install Tesseract and Poppler:

**Ubuntu / Debian:**

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

**macOS (Homebrew):**

```bash
brew install tesseract poppler
```

**Windows:**

- Tesseract: Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
- Poppler: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases)

---

## 6. Start the Application

### Terminal 1 — Backend

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at **http://127.0.0.1:8000**  
Swagger docs at **http://127.0.0.1:8000/docs**

### Terminal 2 — Frontend

```bash
streamlit run frontend/app.py
```

The web UI will open at **http://localhost:8501**

### Terminal 3 — Celery Worker (Optional)

```bash
celery -A backend.celery_app.celery worker --loglevel=info -P solo
```

> **Note**: `-P solo` is required on Windows (no `fork` support). On Linux/macOS, you can omit it.

> Without the Celery worker, document ingestion runs via in-process threads. With it, tasks are distributed through Redis for scalable background processing.

---

## 7. Verify Installation

1. Open http://localhost:8501 in your browser
2. Upload a test document (PDF, Markdown, or text)
3. Click **Upload & Index**
4. Wait for "All document chunks ingested successfully"
5. Ask a question about the document
6. Verify you receive an answer with citations and a confidence score

---

## 8. Using the Makefile

For convenience, use the included Makefile shortcuts:

```bash
make install    # Install all dependencies
make backend    # Start the FastAPI backend server
make frontend   # Start the Streamlit frontend
make worker     # Start Celery worker (uses -P solo for Windows)
make docker-up  # Build and start all services with Docker Compose
make docker-down # Stop all Docker services
make clean      # Remove generated Python cache files
```

---

## 9. Troubleshooting

### "ModuleNotFoundError"

Ensure your virtual environment is activated and dependencies are installed:

```bash
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### "Backend not reachable" in Streamlit

The backend must be running before the frontend. Start the backend first:

```bash
uvicorn backend.main:app --reload
```

### "GROQ_API_KEY not set" or "SUPABASE_URL not set"

Ensure your `.env` file exists and contains all required variables:

```bash
cat .env
# Should show: GROQ_API_KEY=gsk_..., SUPABASE_URL=..., SUPABASE_KEY=...
```

### Slow first startup

The first run downloads the embedding model (~80 MB). Subsequent starts will be fast.

### OCR not working

Verify Tesseract is installed: `tesseract --version`  
Verify Poppler is installed: `pdftoppm -h`

### Ingestion stuck at "running"

- If using Celery: Ensure the worker is running (`make worker`)
- If not using Celery: Check backend terminal for error logs
- Workaround: Set `USE_CELERY=false` in `.env` to use in-process threads

### Redis connection errors

- For local Redis: Ensure Redis server is running (`redis-server` or Docker)
- For Upstash: Ensure `REDIS_URL` starts with `rediss://` (note the double `s` for TLS)
- Fallback: Set `USE_CELERY=false` to skip Redis entirely
