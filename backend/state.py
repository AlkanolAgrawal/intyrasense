import os
import logging
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# In-memory fallback
_in_memory_status = {"state": "idle"}

# Redis connection (lazy / safe)
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3, decode_responses=True)
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = False
    return _redis_client if _redis_client is not False else None


def set_ingestion_status(state: str, task_id: str | None = None):
    """
    Update ingestion status in Redis (if available) and in-memory fallback.
    """
    _in_memory_status["state"] = state
    if task_id:
        _in_memory_status["task_id"] = task_id

    r = _get_redis()
    if r:
        try:
            r.set("ingestion:status", state, ex=86400)
            if task_id:
                r.set(f"ingestion:task:{task_id}", state, ex=86400)
        except Exception as e:
            logger.debug(f"Failed to update Redis ingestion status: {e}")


def get_ingestion_status(task_id: str | None = None) -> dict:
    """
    Retrieve ingestion status. Supports per-task status or global latest status.
    Seamlessly falls back to in-memory status if Redis is unavailable.
    """
    # 1. If task_id is provided, check Celery AsyncResult or Redis task key
    if task_id:
        try:
            from celery.result import AsyncResult
            from backend.celery_app import celery
            res = AsyncResult(task_id, app=celery)
            celery_state = res.state.upper()
            state_map = {
                "PENDING": "running",
                "STARTED": "running",
                "RUNNING": "running",
                "RETRY": "running",
                "SUCCESS": "completed",
                "FAILURE": "failed",
            }
            if celery_state in state_map:
                return {"state": state_map[celery_state], "task_id": task_id}
        except Exception:
            pass

        r = _get_redis()
        if r:
            try:
                val = r.get(f"ingestion:task:{task_id}")
                if val:
                    return {"state": val, "task_id": task_id}
            except Exception:
                pass

    # 2. Check Redis for global latest status
    r = _get_redis()
    if r:
        try:
            val = r.get("ingestion:status")
            if val:
                return {"state": val}
        except Exception:
            pass

    # 3. Fallback to in-memory state
    return dict(_in_memory_status)