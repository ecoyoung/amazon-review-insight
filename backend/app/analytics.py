from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .queueing import get_redis


router = APIRouter(prefix="/api/analytics", tags=["analytics"])

METRICS_KEY = "amazon-review-insight:analytics:metrics"
SESSIONS_KEY = "amazon-review-insight:analytics:sessions"
VISITS_KEY = "amazon-review-insight:analytics:visits"
IPS_KEY = "amazon-review-insight:analytics:ips"
EVENTS_KEY = "amazon-review-insight:analytics:events"
MAX_EVENTS = 500


class AnalyticsEvent(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    session_id: str = Field(..., min_length=8, max_length=128)
    visit_id: str | None = Field(default=None, max_length=128)
    path: str | None = Field(default=None, max_length=256)
    job_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _redis() -> Any:
    return get_redis()


def _now() -> float:
    return time.time()


def client_ip_from_request(request: Request) -> str | None:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


def require_admin_token(authorization: str | None) -> None:
    expected = os.getenv("ANALYTICS_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Analytics admin token is not configured.",
        )
    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid analytics admin token.")


def track_event(
    event_type: str,
    *,
    session_id: str | None = None,
    visit_id: str | None = None,
    path: str | None = None,
    job_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    redis = _redis()
    now = _now()
    pipe = redis.pipeline()
    pipe.hincrby(METRICS_KEY, f"event:{event_type}", 1)
    if event_type == "page_view":
        pipe.hincrby(METRICS_KEY, "page_views", 1)
    if event_type == "task_submitted":
        pipe.hincrby(METRICS_KEY, "task_submissions", 1)
    if session_id:
        pipe.sadd(SESSIONS_KEY, session_id)
    if visit_id:
        pipe.sadd(VISITS_KEY, visit_id)
    if ip_address:
        pipe.sadd(IPS_KEY, ip_address)
    event = {
        "event_type": event_type,
        "session_id": session_id,
        "visit_id": visit_id,
        "path": path,
        "job_id": job_id,
        "ip_address": ip_address,
        "metadata": metadata or {},
        "timestamp": now,
    }
    pipe.lpush(EVENTS_KEY, json.dumps(event, ensure_ascii=False))
    pipe.ltrim(EVENTS_KEY, 0, MAX_EVENTS - 1)
    pipe.execute()


@router.post("/event")
def record_event(payload: AnalyticsEvent, request: Request) -> dict[str, bool]:
    track_event(
        payload.event_type,
        session_id=payload.session_id,
        visit_id=payload.visit_id,
        path=payload.path,
        job_id=payload.job_id,
        ip_address=client_ip_from_request(request),
        metadata=payload.metadata,
    )
    return {"ok": True}


@router.get("/summary")
def analytics_summary(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_token(authorization)
    redis = _redis()
    metrics = redis.hgetall(METRICS_KEY) or {}
    decoded = {
        (key.decode("utf-8") if isinstance(key, bytes) else str(key)): int(value)
        for key, value in metrics.items()
    }
    raw_events = redis.lrange(EVENTS_KEY, 0, 9) or []
    recent_events = []
    for raw in raw_events:
        try:
            recent_events.append(json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw))
        except Exception:  # noqa: BLE001
            continue
    return {
        "page_views": decoded.get("page_views", 0),
        "unique_visitors": int(redis.scard(SESSIONS_KEY) or 0),
        "unique_ips": int(redis.scard(IPS_KEY) or 0),
        "visits": int(redis.scard(VISITS_KEY) or 0),
        "task_submissions": decoded.get("task_submissions", 0),
        "events": {
            key.removeprefix("event:"): value
            for key, value in decoded.items()
            if key.startswith("event:")
        },
        "recent_events": recent_events,
    }
