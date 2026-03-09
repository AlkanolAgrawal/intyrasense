import os
import shutil
import torch
from pdf2image import convert_from_path
import pytesseract

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ----------------------------
# SYSTEM OPTIMIZATION
# ----------------------------
torch.set_num_threads(os.cpu_count())


# ----------------------------
# DIRECTORIES
# ----------------------------
RAW_DIR = "data/raw_docs"
INDEX_DIR = "data/faiss_index"


# ----------------------------
# EMBEDDING MODEL (LOAD ONCE)
# ----------------------------
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={
        "batch_size": 32,
        "normalize_embeddings": True
    }
)


# ----------------------------
# SMART PDF LOADER
# ----------------------------
def load_pdf_smart(path, min_text_length=100):

    documents = []

    loader = PyPDFLoader(path)
    normal_docs = loader.load()

    normal_text = "\n".join(
        [doc.page_content.strip() for doc in normal_docs]
    ).strip()

    # Use native text if meaningful
    if len(normal_text) >= min_text_length:
        documents.extend(normal_docs)

    # OCR fallback
    if len(normal_text) < min_text_length:

        images = convert_from_path(path)

        ocr_text = ""

        for img in images:
            ocr_text += pytesseract.image_to_string(img) + "\n"

        ocr_text = ocr_text.strip()

        if len(ocr_text) >= min_text_length:
            documents.append(
                Document(
                    page_content=ocr_text,
                    metadata={
                        "source": os.path.basename(path),
                        "type": "ocr"
                    }
                )
            )

    return documents


# ----------------------------
# LOAD ALL DOCUMENTS
# ----------------------------
def load_documents():

    docs = []

    if not os.path.exists(RAW_DIR):
        return docs

    for file in os.listdir(RAW_DIR):

        path = os.path.join(RAW_DIR, file)

        if file.endswith(".pdf"):
            loaded = load_pdf_smart(path)

        elif file.endswith(".md"):
            loaded = UnstructuredMarkdownLoader(path).load()

        elif file.endswith(".txt"):
            loaded = TextLoader(path).load()

        else:
            continue

        for d in loaded:
            d.metadata["source"] = file

        docs.extend(loaded)

    return docs


# ----------------------------
# INGEST PIPELINE
# ----------------------------
def ingest_documents():

    # remove old index
    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)

    documents = load_documents()

    if not documents:
        print("No documents found.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=250
    )

    document_chunks = text_splitter.split_documents(documents)

    vector_store = FAISS.from_documents(
        document_chunks,
        embedding_model
    )

    vector_store.save_local(INDEX_DIR)

    print(f"Ingested {len(document_chunks)} chunks.")