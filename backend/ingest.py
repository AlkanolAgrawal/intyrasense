import os
import torch
import tempfile
from pdf2image import convert_from_path
import pytesseract

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

INSERT_BATCH = 200
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
# ----------------------------
def load_documents():

    docs = []

    files = supabase.storage.from_(BUCKET_NAME).list()

    for f in files:

        filename = f["name"]

        print(f"Downloading {filename}...")

        file_bytes = supabase.storage.from_(BUCKET_NAME).download(filename)

        tmp = tempfile.NamedTemporaryFile(delete=False)

        tmp.write(file_bytes)
        tmp.close()

        path = tmp.name

        if filename.endswith(".pdf"):
            loaded = load_pdf_smart(path)

        elif filename.endswith(".md"):
            loaded = UnstructuredMarkdownLoader(path).load()

        elif filename.endswith(".txt"):
            loaded = TextLoader(path).load()

        else:
            continue

        for d in loaded:
            d.metadata["source"] = filename

        docs.extend(loaded)

    return docs


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

        if not text:
            continue

        texts.append(text)
        sources.append(chunk.metadata.get("source", "unknown"))
        pages.append(chunk.metadata.get("page", 1))

    # ----------------------------
    # CREATE EMBEDDINGS
    # ----------------------------
    vectors = embeddings().embed_documents(texts)

    # ----------------------------
    # DOCUMENT IDS
    # ----------------------------
    doc_id_map = {}

    unique_docs = set(sources)

    for doc in unique_docs:

        ext = doc.split(".")[-1]

        res = (
            supabase.table("documents")
            .select("id")
            .eq("name", doc)
            .execute()
        )

        if res.data:
            doc_id = res.data[0]["id"]

        else:
            res = supabase.table("documents").insert({
                "name": doc,
                "type": ext
            }).execute()

            doc_id = res.data[0]["id"]

        doc_id_map[doc] = doc_id

        # delete previous chunks for re-ingest
        (
            supabase.table("chunks")
            .delete()
            .eq("source", doc_id)
            .execute()
        )

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
            "source": doc_id_map[source],
            "page": page,
            "text": text,
            "embedding": vector.tolist()
        })

    # ----------------------------
    # BATCH INSERT
    # ----------------------------
    for i in range(0, len(records), INSERT_BATCH):

        batch = records[i:i + INSERT_BATCH]

        supabase.table("chunks").insert(batch).execute()

    print(f"Ingested {len(records)} chunks into Supabase.")