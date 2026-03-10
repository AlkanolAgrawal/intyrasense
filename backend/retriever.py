from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import os

INDEX_DIR = "data/faiss_index"

# Ensure directory exists
os.makedirs(INDEX_DIR, exist_ok=True)

# ----------------------------
# EMBEDDINGS (LOAD ONCE)
# ----------------------------
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
    encode_kwargs={
        "batch_size": 32,
        "normalize_embeddings": True
    }
)

# ----------------------------
# LOAD FAISS INDEX (SAFE)
# ----------------------------
db = None

def load_index():
    global db

    index_file = os.path.join(INDEX_DIR, "index.faiss")

    if os.path.exists(index_file):
        db = FAISS.load_local(
            INDEX_DIR,
            embeddings,
            allow_dangerous_deserialization=True
        )
        print("FAISS index loaded.")
    else:
        db = None
        print("No FAISS index found. Waiting for ingestion.")

load_index()


# ----------------------------
# RETRIEVAL FUNCTION
# ----------------------------
def retrieve_with_score(query: str, document: str | None = None):

    global db

    if db is None:
        print("FAISS index empty.")
        return []

    if document:
        results = db.similarity_search_with_score(
            query,
            k=50,
            filter={"source": document}
        )
    else:
        results = db.similarity_search_with_score(
            query,
            k=10
        )

    return results


# ----------------------------
# RELOAD INDEX AFTER INGEST
# ----------------------------
def reload_index():
    load_index()