from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = "data/faiss_index"


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
# LOAD FAISS INDEX
# ----------------------------
db = FAISS.load_local(
    INDEX_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)


# ----------------------------
# RETRIEVAL FUNCTION
# ----------------------------
def retrieve_with_score(query: str, document: str | None = None):

    print("Selected:", document)

    # get indexed sources
    sources = {
        d.metadata.get("source")
        for d in db.docstore._dict.values()
    }

    print("Indexed sources:", sources)

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

    global db

    db = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    print("FAISS index reloaded.")