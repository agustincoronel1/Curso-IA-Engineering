"""Integración activa con LangSmith (tracing automático de LangGraph/LangChain)."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

PROMPT_VERSION = "pre7-v1"
RECURSION_LIMIT = 25
logger = logging.getLogger("observability")


def langsmith_enabled() -> bool:
    tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true"
    return tracing and bool(os.getenv("LANGSMITH_API_KEY"))


def log_langsmith_status() -> None:
    if langsmith_enabled():
        logger.warning("LangSmith ACTIVO. Proyecto=%s", os.getenv("LANGSMITH_PROJECT", "default"))
    else:
        logger.warning("LangSmith INACTIVO: definir LANGSMITH_TRACING=true y LANGSMITH_API_KEY.")


def build_config(job_id: str, resumed: bool = False) -> dict:
    """Config del grafo: thread_id = job_id + metadata/tags para filtrar en LangSmith."""
    return {
        "configurable": {"thread_id": job_id},
        "recursion_limit": RECURSION_LIMIT,
        "run_name": "orchestrator_resume" if resumed else "orchestrator",
        "tags": ["pre-entrega-7", f"job:{job_id}"],
        "metadata": {
            "job_id": job_id,
            "thread_id": job_id,
            "prompt_version": PROMPT_VERSION,
            "resumed": resumed,
        },
    }
