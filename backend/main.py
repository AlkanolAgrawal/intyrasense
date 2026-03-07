from dotenv import load_dotenv
load_dotenv(override=True)

import os
from fastapi import FastAPI, UploadFile, File
import shutil
from backend.ingest import ingest_documents
from backend.qa import answer_question, summarize_documents
from backend.utils import list_documents
app = FastAPI()

UPLOAD_DIR = "data/raw_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from pydantic import BaseModel

class QueryRequest(BaseModel):
    question: str
    chat_history: list = []

class SummarizeRequest(BaseModel):
    document: str
@app.post("/upload")
async def upload_docs(files: list[UploadFile] = File(...)):
    """
    Upload and index documents.
    """
    for file in files:
        # file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in {".pdf", ".md", ".txt"}:
            return {"error": f"Unsupported file type: {file_extension}"}

        # Save file to upload directory
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    # Rebuild 
    ingest_documents()
    return {"status": "Index rebuilt successfully"}

@app.post("/query")
async def query(payload: dict):
    return answer_question(
        payload.get("question", ""),
        payload.get("chat_history", []),
        payload.get("document")
    )

@app.post("/summarize")
async def summarize(payload: dict):
    return summarize_documents(payload.get("document"))


@app.get("/documents")
async def get_documents():
    return {"documents": list_documents()}