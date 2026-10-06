"""Estado compartido del orquestador multi-agente."""

import operator
from typing import Annotated, Literal, Optional

from langgraph.graph import MessagesState


NextAgent = Literal["researcher", "analyst", "synthesizer", "FINISH"]


class OrchestratorState(MessagesState):
    """Estado global que comparten Supervisor y especialistas.

    `MessagesState` ya aporta `messages` con el reducer `add_messages`.
    Los campos propios permiten conservar resultados por especialista,
    registrar decisiones del Supervisor y evitar pérdida de contexto.
    """

    user_request: str
    next_agent: NextAgent

    research_result: Optional[str]
    analysis_result: Optional[str]
    final_answer: Optional[str]

    # Feedback explícito del Supervisor para que un especialista pueda
    # refinar su salida en una segunda intervención.
    supervisor_feedback: Optional[str]

    # Cada especialista agrega únicamente su aporte nuevo.
    contributions: Annotated[list[dict], operator.add]

    # Cantidad de decisiones tomadas por el Supervisor.
    steps: int
    task_completed: bool

    # Trazabilidad legible de las decisiones y validaciones del Supervisor.
    validation_notes: Annotated[list[str], operator.add]
