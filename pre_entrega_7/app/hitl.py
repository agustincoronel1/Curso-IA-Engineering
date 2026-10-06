"""Criterio determinista de tarea crítica y nodo de aprobación (interrupt real)."""

import os
from typing import Literal

from langgraph.types import interrupt

from app.state import OrchestratorState


def cost_threshold() -> float:
    return float(os.getenv("HITL_COST_THRESHOLD") or 10000)


def is_critical(estimated_cost: float | None) -> bool:
    return estimated_cost is not None and estimated_cost >= cost_threshold()


def nodo_approval_gate(state: OrchestratorState) -> dict:
    """Pausa el grafo con interrupt() si la tarea es crítica; se reanuda con Command(resume=...)."""

    cost = state.get("estimated_cost")
    if not is_critical(cost):
        return {"rejected": False}

    decision = interrupt(
        {
            "motivo": "Tarea crítica: estimated_cost >= HITL_COST_THRESHOLD",
            "estimated_cost": cost,
            "threshold": cost_threshold(),
            "solicitud": state["user_request"],
        }
    )
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
    note = f"HITL: tarea crítica (costo {cost}); {'APROBADA' if approved else 'RECHAZADA'} por humano."
    if isinstance(decision, dict) and decision.get("comment"):
        note += f" Comentario: {decision['comment']}"
    return {"rejected": not approved, "validation_notes": [note]}


def route_after_gate(state: OrchestratorState) -> Literal["supervisor", "__end__"]:
    return "__end__" if state.get("rejected") else "supervisor"
