import os
import torch
import tempfile
from pdf2image import convert_from_path
import pytesseract
from backend.utils import file_hash
from concurrent.futures import ThreadPoolExecutor

from backend.models import embeddings
from backend.supabase_client import supabase

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter



torch.set_num_threads(os.cpu_count())

INSERT_BATCH = 1000
BUCKET_NAME = "documents"


# ----------------------------
# SMART PDF LOADER
# ----------------------------
def load_pdf_smart(path, min_text_length=100):

    loader = PyPDFLoader(path)
    normal_docs = loader.load()
    normal_text = "\n".join(
        d.page_content.strip() for d in normal_docs
    ).strip()

    if len(normal_text) >= min_text_length:
        return normal_docs

    images = convert_from_path(path)

    docs = []

    for i, img in enumerate(images):

        text = pytesseract.image_to_string(img).strip()

        if text:
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": os.path.basename(path),
                        "page": i + 1
                    }
                )
            )

    return docs


# ----------------------------
# LOAD DOCUMENTS FROM BUCKET
# -----------------------------

def load_documents():
    
    docs = []

    files = supabase.storage.from_(BUCKET_NAME).list()

    for f in files:

        filename = f["name"]

        print(f"Downloading {filename}...")

        file_bytes = supabase.storage.from_(BUCKET_NAME).download(filename)

        hash_value = file_hash(file_bytes)

        # -----------------------------
        # DUPLICATE CHECK
        # -----------------------------
        res = (
            supabase.table("documents")
            .select("id")
            .eq("file_hash", hash_value)
            .execute()
        )

        if res.data:
            print(f"Skipping duplicate file: {filename}")
            continue

        # -----------------------------
        # INSERT DOCUMENT
        # -----------------------------
        ext = filename.split(".")[-1].lower()

        res = supabase.table("documents").insert({
            "name": filename,
            "type": ext,
            "file_hash": hash_value
        }).execute()

        doc_id = res.data[0]["id"]

        # -----------------------------
        # TEMP FILE
        # -----------------------------
        tmp = tempfile.NamedTemporaryFile(delete=False)

        tmp.write(file_bytes)
        tmp.close()

        path = tmp.name

        try:

            # -----------------------------
            # LOAD DOCUMENT
            # -----------------------------
            if ext == "pdf":
                loaded = load_pdf_smart(path)

            elif ext == "md":
                loaded = UnstructuredMarkdownLoader(path).load()

            elif ext == "txt":
                loaded = TextLoader(path).load()

            else:
                continue

            # -----------------------------
            # METADATA
            # -----------------------------
            for d in loaded:

                d.metadata["source"] = doc_id
                d.metadata["filename"] = filename

                # ensure page exists
                if "page" not in d.metadata:
                    d.metadata["page"] = 1

            docs.extend(loaded)

        finally:
            os.remove(path)

    return docs


# ----------------------------
# PARALLEL EMBEDDING
# -----------------------------
model = embeddings()
def embed_parallel(texts, batch_size=64, workers=4):

    batches = [
        texts[i:i + batch_size]
        for i in range(0, len(texts), batch_size)
    ]

    def process(batch):
        return model.embed_documents(batch)

    vectors = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(process, batches)

        for r in results:
            vectors.extend(r)

    return vectors
# ----------------------------
# INGEST PIPELINE
# ----------------------------
def ingest_documents():

    documents = load_documents()

    if not documents:
        print("No documents found.")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=250
    )

    chunks = splitter.split_documents(documents)

    print(f"Processing {len(chunks)} chunks...")

    texts = []
    sources = []
    pages = []

    for chunk in chunks:

        text = chunk.page_content.strip()

        if len(text) < 20:
            continue

        texts.append(text)
        sources.append(chunk.metadata.get("source", "unknown"))
        pages.append(chunk.metadata.get("page", 1))
    
    # ----------------------------
    # CREATE EMBEDDINGS
    # ----------------------------
    if not texts:
        print("No valid chunks.")
        return
    vectors = embed_parallel(texts)
    # ----------------------------
    # BUILD CHUNK RECORDS
    # ----------------------------
    records = []

    for text, vector, source, page in zip(
        texts,
        vectors,
        sources,
        pages
    ):

        records.append({
            "source": source,
            "page": page,
            "text": text,
            "embedding": vector.tolist()
        })

    # ----------------------------
    # BATCH INSERT
    # ----------------------------
    for i in range(0, len(records), INSERT_BATCH):

        batch = records[i:i + INSERT_BATCH]

        try:
            supabase.table("chunks").insert(batch).execute()
        except Exception as e:
            print("Insert error:", e)

    print(f"Ingested {len(records)} chunks into Supabase.")