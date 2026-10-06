"""Estado de jobs y cola de tareas en Redis (redis.asyncio)."""

import json
import os
import time
from typing import Any, Optional

from redis import asyncio as aioredis

from app.schemas import JobStatus

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = "queue:tasks"


def job_key(job_id: str) -> str:
    return f"job:{job_id}"


def get_redis() -> aioredis.Redis:
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def create_job(r: aioredis.Redis, job_id: str, payload: dict) -> None:
    """Persiste el job como PENDING (siempre ANTES de encolar)."""
    await r.hset(
        job_key(job_id),
        mapping={
            "status": JobStatus.PENDING.value,
            "input": json.dumps(payload),
            "created_at": time.time(),
        },
    )


async def update_job(r: aioredis.Redis, job_id: str, status: JobStatus, **fields: Any) -> None:
    mapping = {"status": status.value, "updated_at": time.time()}
    for k, v in fields.items():
        mapping[k] = json.dumps(v) if not isinstance(v, str) else v
    await r.hset(job_key(job_id), mapping=mapping)


async def get_job(r: aioredis.Redis, job_id: str) -> Optional[dict]:
    data = await r.hgetall(job_key(job_id))
    if not data:
        return None
    return {
        "job_id": job_id,
        "status": data["status"],
        "input": json.loads(data["input"]),
        "result": json.loads(data["result"]) if data.get("result") else None,
        "error": data.get("error"),
        "approval_request": json.loads(data["approval_request"]) if data.get("approval_request") else None,
    }


async def enqueue(r: aioredis.Redis, message: dict) -> None:
    await r.lpush(QUEUE_KEY, json.dumps(message))


async def dequeue(r: aioredis.Redis, timeout: int = 2) -> Optional[dict]:
    item = await r.brpop(QUEUE_KEY, timeout=timeout)
    return json.loads(item[1]) if item else None
