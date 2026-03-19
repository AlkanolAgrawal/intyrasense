from backend.supabase_client import supabase
import hashlib
def list_documents():
    res = (
        supabase
        .table("documents")
        .select("name, storage_path")
        .execute()
    )
    if not res.data:
        return []
    return sorted(res.data, key=lambda x: x["storage_path"])  ##returns sorted list of docs(id,name) by name

def file_hash(data: bytes):
    return hashlib.sha256(data).hexdigest()

def get_doc_id_from_name(name):
    res = (supabase.table("documents") 
        .select("id") 
        .eq("storage_path", name) 
        .limit(1) 
        .execute()
    )
    return res.data[0]["id"] if res.data else None