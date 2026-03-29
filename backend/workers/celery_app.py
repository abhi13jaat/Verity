import ssl

from celery import Celery

from backend.core.config import settings

celery_app = Celery(
    "verity",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.workers.tasks"],
)

_conf = dict(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)

# Managed Redis (Upstash, etc.) uses rediss:// (TLS). Celery needs explicit SSL
# options for both the broker and the result backend.
if settings.redis_url.startswith("rediss://"):
    _conf["broker_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}
    _conf["redis_backend_use_ssl"] = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app.conf.update(**_conf)
