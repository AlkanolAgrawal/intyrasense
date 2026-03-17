from backend.supabase_client import supabase
import hashlib
def list_documents():

    res = (
        supabase
        .table("documents")
        .select("id, name")
        .execute()
    )

    if not res.data:
        return []

    return sorted(res.data, key=lambda x: x["name"])

def file_hash(data: bytes):
    return hashlib.sha256(data).hexdigest()


ingestion_status = {
    "state": "idle"
}

def set_ingestion_status(state: str):
    ingestion_status["state"] = state

def get_ingestion_status():
    return ingestion_status