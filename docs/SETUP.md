# 🛠️ Setup Guide

> Step-by-step instructions to get INTYRASENSE running locally.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Tested with 3.11 and 3.12 |
| pip | Latest | `pip install --upgrade pip` |
| Groq API Key | — | [Get one free](https://console.groq.com) |
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
source venv/bin/activate  # Linux / macOS
# venv\Scripts\activate   # Windows
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

Edit `.env` and set your Groq API key and Supabase credentials:

```env
GROQ_API_KEY=gsk_your_actual_key_here
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_supabase_key_here
```

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
uvicorn backend.main:app --reload
```

The API will be available at **http://127.0.0.1:8000**  
Swagger docs at **http://127.0.0.1:8000/docs**

### Terminal 2 — Frontend

```bash
streamlit run frontend/app.py
```

The web UI will open at **http://localhost:8501**

---

## 7. Verify Installation

1. Open http://localhost:8501 in your browser
2. Upload a test document (PDF, Markdown, or text)
3. Click **Upload & Index**
4. Ask a question about the document
5. Verify you receive an answer with citations and a confidence score

---

## 8. Using the Makefile

For convenience, use the included Makefile shortcuts:

```bash
make install    # Install all dependencies
make run        # Start backend + frontend (requires two terminals)
make backend    # Start backend only
make frontend   # Start frontend only
make docker-up  # Start with Docker Compose
make clean      # Remove generated Python cache files
```

---

## 9. Troubleshooting

### "ModuleNotFoundError"

Ensure your virtual environment is activated and dependencies are installed:

```bash
source venv/bin/activate
pip install -r requirements.txt
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
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
