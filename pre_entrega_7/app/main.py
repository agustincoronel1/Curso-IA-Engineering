"""API FastAPI asíncrona: encola tareas y expone estado/aprobación."""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from langgraph.checkpoint.redis.aio import AsyncRedisSaver  # noqa: E402

from app import redis_client as rc  # noqa: E402
from app.graph import construir_grafo  # noqa: E402
from app.hitl import cost_threshold  # noqa: E402
from app.observability import log_langsmith_status  # noqa: E402
from app.schemas import (  # noqa: E402
    ApprovalRequest,
    JobStatus,
    TaskCreated,
    TaskRequest,
    TaskStatus,
)
from app.worker import worker_loop  # noqa: E402

WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "5"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    log_langsmith_status()
    r = rc.get_redis()
    app.state.redis = r
    async with AsyncRedisSaver.from_conn_string(rc.REDIS_URL) as checkpointer:
        graph = construir_grafo(checkpointer)
        workers = [asyncio.create_task(worker_loop(graph, r)) for _ in range(WORKER_CONCURRENCY)]
        try:
            yield
        finally:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
    await r.aclose()


app = FastAPI(title="Pre-entrega 7 - Orquestador multi-agente", lifespan=lifespan)


@app.post("/tasks", response_model=TaskCreated, status_code=202)
async def create_task(body: TaskRequest):
    r = app.state.redis
    job_id = str(uuid.uuid4())
    await rc.create_job(r, job_id, body.model_dump())  # 1) persistir PENDING
    await rc.enqueue(r, {"job_id": job_id})  # 2) recién después encolar
    return TaskCreated(job_id=job_id, status=JobStatus.PENDING)


@app.get("/tasks/{job_id}", response_model=TaskStatus)
async def get_task(job_id: str):
    job = await rc.get_job(app.state.redis, job_id)
    if job is None:
        raise HTTPException(404, "job_id inexistente")
    return job


@app.post("/tasks/{job_id}/approve", response_model=TaskCreated, status_code=202)
async def approve_task(job_id: str, body: ApprovalRequest):
    r = app.state.redis
    job = await rc.get_job(r, job_id)
    if job is None:
        raise HTTPException(404, "job_id inexistente")
    if job["status"] != JobStatus.WAITING_APPROVAL.value:
        raise HTTPException(409, f"El job está en {job['status']}; no espera aprobación.")
    await rc.update_job(r, job_id, JobStatus.RUNNING)  # evita doble aprobación
    await rc.enqueue(r, {"job_id": job_id, "resume": body.model_dump()})
    return TaskCreated(job_id=job_id, status=JobStatus.RUNNING)


@app.get("/health")
async def health():
    return {"ok": True, "hitl_cost_threshold": cost_threshold()}
