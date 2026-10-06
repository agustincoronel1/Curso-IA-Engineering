"""Worker async: consume la cola de Redis y ejecuta el grafo LangGraph."""

import asyncio
import logging

from langgraph.types import Command

from app.observability import build_config
from app.redis_client import dequeue, get_job, update_job
from app.schemas import JobStatus

logger = logging.getLogger("worker")


def _result_from_state(values: dict) -> dict:
    return {
        "final_answer": values.get("final_answer"),
        "research_result": values.get("research_result"),
        "analysis_result": values.get("analysis_result"),
        "validation_notes": values.get("validation_notes", []),
        "steps": values.get("steps"),
        "task_completed": values.get("task_completed", False),
        "rejected": values.get("rejected", False),
    }


async def process_message(graph, r, message: dict) -> None:
    job_id = message["job_id"]
    resume = message.get("resume")
    try:
        await update_job(r, job_id, JobStatus.RUNNING)
        job = await get_job(r, job_id)
        config = build_config(job_id, resumed=resume is not None)
        if resume is not None:
            graph_input = Command(resume=resume)  # reanuda el mismo thread_id/checkpoint
        else:
            payload = job["input"]
            graph_input = {
                "messages": [("user", payload["query"])],
                "user_request": payload["query"],
                "next_agent": "researcher",
                "research_result": None,
                "analysis_result": None,
                "final_answer": None,
                "supervisor_feedback": None,
                "contributions": [],
                "steps": 0,
                "task_completed": False,
                "validation_notes": [],
                "estimated_cost": payload.get("estimated_cost"),
                "rejected": False,
            }
        result = await graph.ainvoke(graph_input, config=config)

        interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
        if interrupts:
            await update_job(
                r, job_id, JobStatus.WAITING_APPROVAL, approval_request=interrupts[0].value
            )
            return

        snapshot = await graph.aget_state(config)
        values = snapshot.values
        if not values.get("rejected") and not values.get("final_answer"):
            raise RuntimeError("El grafo terminó sin respuesta final.")
        await update_job(r, job_id, JobStatus.DONE, result=_result_from_state(values))
    except asyncio.CancelledError:
        await update_job(r, job_id, JobStatus.FAILED, error="Worker cancelado antes de terminar.")
        raise
    except Exception as exc:
        logger.exception("Job %s falló", job_id)
        await update_job(r, job_id, JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")


async def worker_loop(graph, r) -> None:
    while True:
        message = await dequeue(r, timeout=2)
        if message is not None:
            await process_message(graph, r, message)
