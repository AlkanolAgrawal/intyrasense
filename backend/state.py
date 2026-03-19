ingestion_status = {"state": "idle"}

def set_ingestion_status(state: str):
    ingestion_status["state"] = state

def get_ingestion_status():
    return ingestion_status