from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

INDEX_DIR = "data/faiss_index"

def get_retriever(document: str | None = None):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    db = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )
    
    if document:
        return db.as_retriever(
            search_kwargs={
                "k": 5,
                "filter": {"source": document}
            }
        )

    return db.as_retriever(search_kwargs={"k": 4})

def retrieve_with_score(query: str, document: str | None = None, k: int = 5):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    db = FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    if document:
        results = db.similarity_search_with_score(
            query,
            k=k,
            filter={"source": document}
        )
    else:
        results = db.similarity_search_with_score(query, k=k)

    return results
