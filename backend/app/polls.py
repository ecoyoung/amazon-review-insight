"""Tiny live-poll API backed by Redis.

A poll has an id, a question, and N options. Clients POST a vote; anyone
can GET the tally. Used by the Slidev course for warm-up / mid-lecture
audience participation. Votes are anonymous (one per browser, enforced
client-side via localStorage — not a hard guarantee, good enough for
internal training).
"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .queueing import get_redis


router = APIRouter(prefix="/api/polls", tags=["polls"])


POLL_KEY = "amazon-review-insight:poll:{poll_id}"
POLL_META_KEY = "amazon-review-insight:poll:{poll_id}:meta"


class PollOption(BaseModel):
    id: str
    label: str


class PollDefinition(BaseModel):
    id: str
    question: str
    options: list[PollOption]


class VotePayload(BaseModel):
    option_id: str = Field(..., min_length=1, max_length=64)


_BUILTIN_POLLS: dict[str, PollDefinition] = {
    "warmup-first-step": PollDefinition(
        id="warmup-first-step",
        question="老板给你 50 万做下一个品类，你的第一步会做什么？",
        options=[
            PollOption(id="report", label="看市场规模报告"),
            PollOption(id="ask", label="问同事 / 老员工"),
            PollOption(id="reviews", label="读头部竞品评论"),
            PollOption(id="data", label="查销量 / 排名数据"),
        ],
    ),
    "use-case-priority": PollDefinition(
        id="use-case-priority",
        question="你最想用 CI 回答哪类问题？",
        options=[
            PollOption(id="select", label="选品 / 品类判断"),
            PollOption(id="optimize", label="产品优化"),
            PollOption(id="content", label="内容 / 广告脚本"),
            PollOption(id="competitor", label="竞品分析"),
        ],
    ),
    "method-first-move": PollDefinition(
        id="method-first-move",
        question="1000 条评论摆在你面前，你的第一步？",
        options=[
            PollOption(id="read-all", label="一条一条读"),
            PollOption(id="define", label="先写下业务问题"),
            PollOption(id="sample", label="随机抽 50 条看"),
            PollOption(id="tool", label="直接丢给工具"),
        ],
    ),
}


def _redis() -> Any:
    return get_redis()


def _load_poll(poll_id: str) -> PollDefinition:
    if poll_id in _BUILTIN_POLLS:
        return _BUILTIN_POLLS[poll_id]
    raw = _redis().get(POLL_META_KEY.format(poll_id=poll_id))
    if not raw:
        raise HTTPException(status_code=404, detail=f"Poll '{poll_id}' not found")
    return PollDefinition(**json.loads(raw))


@router.get("", response_model=list[PollDefinition])
def list_polls() -> list[PollDefinition]:
    return list(_BUILTIN_POLLS.values())


@router.get("/{poll_id}", response_model=PollDefinition)
def get_poll(poll_id: str) -> PollDefinition:
    return _load_poll(poll_id)


@router.post("/{poll_id}/vote")
def cast_vote(poll_id: str, payload: VotePayload) -> dict[str, Any]:
    poll = _load_poll(poll_id)
    valid_ids = {opt.id for opt in poll.options}
    if payload.option_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Invalid option_id '{payload.option_id}'")
    key = POLL_KEY.format(poll_id=poll_id)
    _redis().hincrby(key, payload.option_id, 1)
    return {"ok": True, "poll_id": poll_id, "option_id": payload.option_id}


@router.get("/{poll_id}/results")
def get_results(poll_id: str) -> dict[str, Any]:
    poll = _load_poll(poll_id)
    key = POLL_KEY.format(poll_id=poll_id)
    raw = _redis().hgetall(key) or {}
    counts = {k.decode("utf-8"): int(v) for k, v in raw.items()}
    total = sum(counts.values())
    options = []
    for opt in poll.options:
        c = counts.get(opt.id, 0)
        options.append({
            "id": opt.id,
            "label": opt.label,
            "count": c,
            "pct": round(c * 100 / total, 1) if total else 0.0,
        })
    return {
        "poll_id": poll_id,
        "question": poll.question,
        "total": total,
        "options": options,
        "server_time": time.time(),
    }
