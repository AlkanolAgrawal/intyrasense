from fastapi import FastAPI, UploadFile, File
import os
import shutil
from dotenv import load_dotenv

from backend.ingest import ingest_documents
from backend.qa import answer_question, summarize_documents
from backend.utils import list_documents

load_dotenv()

app = FastAPI()

UPLOAD_DIR = "data/raw_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from pydantic import BaseModel

class QueryRequest(BaseModel):
    question: str
    chat_history: list = []

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
async def summarize():
    return summarize_documents()


@app.get("/documents")
async def get_documents():
    return {"documents": list_documents()}