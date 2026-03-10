from functools import lru_cache

from backend.supabase_client import supabase
from backend.models import embeddings


# ---------------------------------
# EMBEDDING CACHE
# ---------------------------------
@lru_cache(maxsize=256)
def embed_query_cached(text: str):
    return embeddings().embed_query(text)


# ---------------------------------
# VECTOR RETRIEVAL
# ---------------------------------
def retrieve_with_score(query: str, document: str | None = None):

    try:

        # create query embedding
        query_embedding = embed_query_cached(query)

        params = {
            "query_embedding": query_embedding,
            "match_count": 6
        }

        # optional document filter
        if document:
            params["document_filter"] = document

        response = supabase.rpc(
            "match_embeddings",
            params
        ).execute()

        if not response.data:
            return []

        return response.data

    except Exception as e:

        print("Retrieval error:", e)

        return []