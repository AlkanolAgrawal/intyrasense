"""
Document Ingestion and Vector Index Creation

This module handles:
1. Loading documents from various formats (PDF, Markdown, Text)
2. Splitting documents into manageable chunks
3. Creating embeddings using sentence transformers
4. Building and saving FAISS vector index for semantic search
"""

import os
import shutil

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Directories for raw documents and vector index
RAW_DIR = "data/raw_docs"
INDEX_DIR = "data/faiss_index"


def load_documents():
    docs = []

    for file in os.listdir(RAW_DIR):
        path = os.path.join(RAW_DIR, file)

        if file.endswith(".pdf"):
            loaded = PyPDFLoader(path).load()
        elif file.endswith(".md"):
            loaded = UnstructuredMarkdownLoader(path).load()
        elif file.endswith(".txt"):
            loaded = TextLoader(path).load()
        else:
            continue

        for d in loaded:
            d.metadata["source"] = file
            # docs.append(d)
        docs.extend(loaded) ##adds all d at once
    return docs


def ingest_documents():
    # Remove existing index to rebuild from scratch
    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)

    # Load all documents
    documents = load_documents()
    if not documents:
        # No documents to index
        return

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100
    )
    document_chunks = text_splitter.split_documents(documents)

    # Initialize embedding model 
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Create FAISS vector store from document chunks
    vector_store = FAISS.from_documents(document_chunks, embedding_model)
    
    # Save the index to disk for persistence
    vector_store.save_local(INDEX_DIR)

