import os
import uuid
import shutil
import threading
import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.ingest import ingest_documents
from backend.qa import answer_question, summarize_documents
from backend.utils import list_documents


# ---------------------------------
# ENV + LOGGING
# ---------------------------------
load_dotenv(override=True)

# ---------------------------------
# APP INIT
# ---------------------------------
app = FastAPI(
    title="INTYRASENSE API",
    description="Document-grounded Q&A and summarization API powered by RAG",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------
# STORAGE
# ---------------------------------
UPLOAD_DIR = "data/raw_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".pdf", ".md", ".txt"}


# ---------------------------------
# REQUEST MODELS
# ---------------------------------
class QueryRequest(BaseModel):
    question: str
    chat_history: list = []
    document: str | None = None


class SummarizeRequest(BaseModel):
    document: str


# ---------------------------------
# HEALTH CHECK
# ---------------------------------
@app.get("/")
def health():
    return {"status": "running"}


# ---------------------------------
# DOCUMENT UPLOAD
# ---------------------------------
@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):

    saved_files = []

    for file in files:

        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in ALLOWED_EXT:
            return {"error": f"Unsupported file type: {ext}"}

        unique_name = f"{uuid.uuid4()}_{file.filename}"

        path = os.path.join(UPLOAD_DIR, unique_name)

        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        saved_files.append(unique_name)

    # run ingestion in background
    threading.Thread(target=ingest_documents).start()

    return {
        "status": "upload_successful",
        "files": saved_files
    }


# ---------------------------------
# QUESTION ANSWERING
# ---------------------------------
@app.post("/query")
async def query_documents(req: QueryRequest):

    result = answer_question(
        question=req.question,
        chat_history=req.chat_history,
        document=req.document
    )

    return result


# ---------------------------------
# DOCUMENT SUMMARIZATION
# ---------------------------------
@app.post("/summarize")
async def summarize_document(req: SummarizeRequest):

    return summarize_documents(req.document)


# ---------------------------------
# LIST DOCUMENTS
# ---------------------------------
@app.get("/documents")
async def get_documents():

    return {
        "documents": list_documents()
    }