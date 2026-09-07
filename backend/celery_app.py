import os
import logging
from dotenv import load_dotenv
from celery import Celery
import redis

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
USE_CELERY = os.getenv("USE_CELERY", "true").lower() in ("true", "1", "yes")

celery = Celery(
    "intyrasense",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.tasks"]
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

# Support Upstash / cloud TLS Redis (rediss://)
if CELERY_BROKER_URL.startswith("rediss://"):
    import ssl
    celery.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

if CELERY_RESULT_BACKEND.startswith("rediss://"):
    import ssl
    celery.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def is_celery_available() -> bool:
    """
    Check if Celery is enabled and the Redis broker is reachable.
    Provides graceful zero-breakage fallback for local execution when Redis is not running.
    """
    if not USE_CELERY:
        return False
    try:
        r = redis.Redis.from_url(CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=3)
        r.ping()
        return True
    except Exception as e:
        logger.debug(f"Redis/Celery broker not reachable: {e}")
        return False
