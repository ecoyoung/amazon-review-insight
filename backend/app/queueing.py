from __future__ import annotations

import os
from datetime import datetime, timezone

from redis import Redis
from rq import Queue


QUEUE_NAME = "amazon-review-insight"
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
JOBS_INDEX_KEY = "amazon-review-insight:jobs"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_redis() -> Redis:
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis(), default_timeout=60 * 60 * 3)


def register_job(job_id: str) -> None:
    get_redis().zadd(JOBS_INDEX_KEY, {job_id: datetime.now(timezone.utc).timestamp()})


def list_job_ids(limit: int = 50) -> list[str]:
    items = get_redis().zrevrange(JOBS_INDEX_KEY, 0, max(limit - 1, 0))
    return [item.decode("utf-8") if isinstance(item, bytes) else str(item) for item in items]
