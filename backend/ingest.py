import os
import shutil
from pdf2image import convert_from_path
import pytesseract

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Directories
RAW_DIR = "data/raw_docs"
INDEX_DIR = "data/faiss_index"


# ----------------------------
# SMART PDF LOADER
# ----------------------------
def load_pdf_smart(path, min_text_length=100):
    """
    1. Extract normal PDF text
    2. If text is too small -> run OCR
    3. Return union of meaningful content
    """
    documents = []

    # Step 1: Try native text extraction
    loader = PyPDFLoader(path)
    normal_docs = loader.load()

    normal_text = "\n".join(
        [doc.page_content.strip() for doc in normal_docs]
    ).strip()

    if len(normal_text) >= min_text_length:
        documents.extend(normal_docs)

    # Step 2: OCR fallback if needed
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
    # Remove old index
    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)

    # Load docs
    documents = load_documents()
    if not documents:
        print("No documents found.")
        return

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=250
    )

    document_chunks = text_splitter.split_documents(documents)

    # Embeddings
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Create vector store
    vector_store = FAISS.from_documents(
        document_chunks,
        embedding_model
    )

    # Persist
    vector_store.save_local(INDEX_DIR)

    print(f"Ingested {len(document_chunks)} chunks.")
