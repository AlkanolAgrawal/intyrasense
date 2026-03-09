from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = "data/faiss_index"

# load embeddings once
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"}
)

# load FAISS index once
db = FAISS.load_local(
    INDEX_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)

def retrieve_with_score(query: str, document: str | None = None):
    global db

    print("Selected:", document)

    all_docs = db.docstore._dict.values()
    print("Indexed sources:")
    print({d.metadata["source"] for d in all_docs})

    if document:
        results = db.similarity_search_with_score(
            query,
            k=50,
            filter={"source": document}
        )
    else:
        results = db.similarity_search_with_score(query, k=10)

    return results


# call this after re-ingesting documents
def reload_index():
    global db
    db = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )