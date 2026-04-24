import os
import uuid
import threading
import warnings
import logging
from fastapi.responses import Response
from backend.utils import file_hash
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client
from backend.ingest import ingest_documents
from backend.qa import answer_question, summarize_documents
from backend.utils import list_documents
from backend.state import get_ingestion_status
from backend.state import set_ingestion_status

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

@app.head("/")
def health_head():
    return Response(status_code=200)

# ---------------------------------
# DOCUMENT Ingestion Status
# ---------------------------------
@app.get("/ingestion-status")
def ingestion_status_api():
    return get_ingestion_status()

# ---------------------------------
# DOCUMENT UPLOAD
# ---------------------------------
@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    bucket = supabase.storage.from_(BUCKET_NAME)
    uploaded_files = []
    existing_files = {f["name"] for f in bucket.list()}

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        try:
            file_bytes = await file.read()
            hash_value = file_hash(file_bytes)
            unique_name = f"{hash_value}_{file.filename}"

            if unique_name in existing_files:
                continue
            
            bucket.upload(
                path=unique_name,
                file=file_bytes,
            )
            uploaded_files.append(unique_name)
            existing_files.add(unique_name)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    if uploaded_files:
        # Mark running before the worker starts so clients never get stuck at idle.
        set_ingestion_status("running")
        threading.Thread(
            target=ingest_documents,
            args=(uploaded_files,), ##unique_names
            daemon=True
        ).start()
        message = "Chunk ingestion started."
    else:
        # Nothing new to index (e.g. duplicate uploads only).
        set_ingestion_status("completed")
        message = "No new files to index."

    return {
        "status": "upload_successful",
        "files": uploaded_files,
        "message": message,
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

# ---------------------------------
# DELETE DOCUMENT
# ---------------------------------
@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    try:
        doc_res = supabase.table("documents") \
            .select("*") \
            .eq("id", doc_id) \
            .execute()

        if not doc_res.data:
            raise HTTPException(404, "Document not found")

        doc = doc_res.data[0]
        file_path = doc.get("storage_path")

        if not file_path:
            raise HTTPException(400, "storage_path missing")

        # delete chunks
        supabase.table("chunks") \
            .delete() \
            .eq("source", doc_id) \
            .execute()

        # delete file
        supabase.storage.from_(BUCKET_NAME).remove([file_path])

        # delete document
        supabase.table("documents") \
            .delete() \
            .eq("id", doc_id) \
            .execute()

        return {"status": "deleted", "doc_id": doc_id}

    except Exception as e:
        raise HTTPException(500, str(e))