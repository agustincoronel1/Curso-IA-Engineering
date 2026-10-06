"""Estado compartido del orquestador (copiado de pre_entrega_6 + campos HITL)."""

import operator
from typing import Annotated, Literal, Optional

from langgraph.graph import MessagesState

NextAgent = Literal["researcher", "analyst", "synthesizer", "FINISH"]


class OrchestratorState(MessagesState):
    user_request: str
    next_agent: NextAgent

    research_result: Optional[str]
    analysis_result: Optional[str]
    final_answer: Optional[str]
    supervisor_feedback: Optional[str]
    contributions: Annotated[list[dict], operator.add]
    steps: int
    task_completed: bool
    validation_notes: Annotated[list[str], operator.add]

    # Human-in-the-loop
    estimated_cost: Optional[float]
    rejected: bool
