import os
import uuid
import threading
import warnings
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from backend.utils import ingestion_status

from backend.ingest import ingest_documents
from backend.qa import answer_question, summarize_documents
from backend.utils import list_documents


# ---------------------------------
# ENV + LOGGING
# ---------------------------------
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
load_dotenv(override=True)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------
# APP INIT
# ---------------------------------
app = FastAPI(debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------
# CONFIG
# ---------------------------------
BUCKET_NAME = "documents"
ALLOWED_EXT = {".pdf", ".md", ".txt"}


# ---------------------------------
# REQUEST MODELS
# ---------------------------------
class QueryRequest(BaseModel):
    question: str
    chat_history: list = []
    document: str | None = None

class SummarizeRequest(BaseModel):
    document: str | None = None

# ---------------------------------
# HEALTH
# ---------------------------------
@app.get("/")
def health():
    return {"status": "running"}
# ---------------------------------
# DOCUMENT Ingestion Status
# ---------------------------------
@app.get("/ingestion-status")
def ingestion_status_api():
    return {"state": ingestion_status["state"]}
# ---------------------------------
# DOCUMENT UPLOAD
# ---------------------------------
@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    bucket = supabase.storage.from_(BUCKET_NAME)
    uploaded_files = []

    for file in files:

        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        try:
            file_bytes = await file.read()

            unique_name = f"{uuid.uuid4()}_{file.filename}"

            bucket.upload(
                path=unique_name,
                file=file_bytes,
                file_options={"upsert": "true"}
            )
            uploaded_files.append(unique_name)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    threading.Thread(
        target=ingest_documents,
        args=(uploaded_files,),
        daemon=True
    ).start()

    return {
        "status": "upload_successful",
        "files": uploaded_files
    }
# ---------------------------------
# QUESTION ANSWERING
# ---------------------------------
@app.post("/query")
async def query_documents(req: QueryRequest):

    if not req.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    return answer_question(
        question=req.question,
        chat_history=req.chat_history,
        document=req.document
    )

# ---------------------------------
# SUMMARIZE
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