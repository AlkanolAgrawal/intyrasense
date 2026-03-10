from backend.supabase_client import supabase
import hashlib
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

def file_hash(data: bytes):
    return hashlib.sha256(data).hexdigest()