import logging
from backend.celery_app import celery
from backend.ingest import ingest_documents
from backend.state import set_ingestion_status

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="backend.tasks.ingest_documents_task")
def ingest_documents_task(self, uploaded_files: list[str]):
    """
    Celery task to ingest uploaded document files in a background worker process.
    """
    logger.info(f"[Task {self.request.id}] Starting document ingestion for: {uploaded_files}")
    self.update_state(
        state="RUNNING",
        meta={"files": uploaded_files, "progress": "Indexing document chunks..."}
    )
    set_ingestion_status("running", task_id=self.request.id)

    try:
        ingest_documents(uploaded_files)
        set_ingestion_status("completed", task_id=self.request.id)
        logger.info(f"[Task {self.request.id}] Completed document ingestion.")
        return {"status": "completed", "files": uploaded_files}
    except Exception as e:
        logger.error(f"[Task {self.request.id}] Ingestion failed: {e}", exc_info=True)
        set_ingestion_status("failed", task_id=self.request.id)
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "files": uploaded_files}
        )
        raise
