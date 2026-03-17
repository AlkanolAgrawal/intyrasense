import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pdf2image import convert_from_path
import pytesseract
from backend.utils import file_hash, set_ingestion_status
from backend.models import embeddings
from backend.supabase_client import supabase
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

BUCKET_NAME = "documents"
INSERT_BATCH = 1000
model = embeddings()


# =====================================================
# SMART PDF LOADER
# =====================================================
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
                    metadata={"page": i + 1}
                )
            )
    return docs


# =====================================================
# LOAD DOCUMENTS
# =====================================================
def load_documents():

    docs = []

    files = supabase.storage.from_(BUCKET_NAME).list()

    for f in files:
        filename = f["name"]
        print(f"Downloading {filename}...")
        file_bytes = supabase.storage.from_(BUCKET_NAME).download(filename)
        hash_value = file_hash(file_bytes)

        # -----------------------------------
        # DUPLICATE CHECK
        # -----------------------------------
        res = (
            supabase.table("documents")
            .select("id")
            .eq("file_hash", hash_value)
            .execute()
        )

        if res.data:
            print(f"Skipping duplicate file: {filename}")
            continue

        ext = filename.split(".")[-1].lower()

        # -----------------------------------
        # INSERT DOCUMENT RECORD
        # -----------------------------------
        
        if "_" not in filename:
            print(f"Skipping invalid filename: {filename}")
            continue

        clean_name = filename.split("_", 1)[1]
        res = supabase.table("documents").insert({
            "storage_path": filename,
            "type": ext,
            "file_hash": hash_value,
            "name": clean_name
        }).execute()

        doc_id = res.data[0]["id"]

        # -----------------------------------
        # TEMP FILE
        # -----------------------------------
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(file_bytes)
        tmp.close()

        path = tmp.name

        try:
            if ext == "pdf":
                loaded = load_pdf_smart(path)

            elif ext == "md":
                loaded = UnstructuredMarkdownLoader(path).load()

            elif ext == "txt":
                loaded = TextLoader(path).load()

            else:
                print(f"Unsupported file type: {ext}")
                continue

            # attach metadata
            for d in loaded:
                d.metadata["source"] = doc_id
                d.metadata["page"] = d.metadata.get("page", 1)

            docs.extend(loaded)

        finally:
            os.remove(path)
    return docs


# =====================================================
# PARALLEL EMBEDDINGS
# =====================================================
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


# =====================================================
# INGEST PIPELINE
# =====================================================
def ingest_documents():
    try:
        set_ingestion_status("running")
        documents = load_documents()
        if not documents:
            print("No new documents to ingest.")
            set_ingestion_status("completed")
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
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
            sources.append(chunk.metadata.get("source"))
            pages.append(chunk.metadata.get("page", 1))

        if not texts:
            print("No valid chunks.")
            set_ingestion_status("completed")
            return

        # -----------------------------------
        # EMBEDDINGS
        # -----------------------------------
        vectors = embed_parallel(texts)
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
                "embedding": vector
            })

        # -----------------------------------
        # BATCH INSERT
        # -----------------------------------
        for i in range(0, len(records), INSERT_BATCH):
            batch = records[i:i + INSERT_BATCH]
            try:
                supabase.table("chunks").insert(batch).execute()
            except Exception as e:
                print("Insert error:", e)

        print(f"✓ Successfully ingested {len(records)} chunks into Supabase.")
        set_ingestion_status("completed")

    except Exception as e:
        print("Ingestion failed:", e)
        set_ingestion_status("failed")