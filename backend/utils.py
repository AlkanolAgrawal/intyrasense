from backend.supabase_client import supabase

def list_documents():

    res = (
        supabase
        .table("documents")
        .select("name")
        .execute()
    )

    if not res.data:
        return []

    return sorted([doc["name"] for doc in res.data])