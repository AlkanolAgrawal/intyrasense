from functools import lru_cache
from backend.supabase_client import supabase
from backend.models import embeddings

model = embeddings()


# -----------------------------
# CACHE QUERY EMBEDDINGS
# -----------------------------
@lru_cache(maxsize=256)
def embed_query_cached(text: str):

    text = text.strip().lower()

    return model.embed_query(text)


# -----------------------------
# RETRIEVE CHUNKS
# -----------------------------
def retrieve_with_score(query: str, document=None, k: int = 10):

    try:
        query_embedding = list(embed_query_cached(query))
        
        params = {
            "query_embedding": query_embedding,
            "match_count": k
        }

        if document:
            params["document_filter"] = document

        response = supabase.rpc(
            "match_embeddings",
            params
        ).execute()

        if not response.data:
            return []

        results = []

        for r in response.data:

            results.append({
                "text": r.get("text"),
                "source": r.get("source"),     # document id
                "page": r.get("page", 1),
                "score": r.get("similarity")
            })

        return results

    except Exception as e:

        print("Retrieval error:", e)

        return []