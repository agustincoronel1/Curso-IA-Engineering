"""Grafo jerárquico de la Pre-entrega 6, async, con puerta HITL y checkpointer."""

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.agents.analyst_agent import crear_agente_analista
from app.agents.research_agent import crear_agente_investigador
from app.hitl import nodo_approval_gate, route_after_gate
from app.state import OrchestratorState

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
MAX_STEPS = 6


class DecisionSupervisor(BaseModel):
    """Decisión estructurada del Supervisor para las aristas condicionales."""

    next_agent: Literal["researcher", "analyst", "synthesizer", "FINISH"] = Field(
        description="Próximo nodo que debe ejecutar el grafo."
    )
    research_sufficient: bool = Field(
        description="True solo si la investigación disponible cumple la rúbrica."
    )
    analysis_sufficient: bool = Field(
        description="True solo si el análisis disponible cumple la rúbrica."
    )
    razon: str = Field(
        description=(
            "Explicación breve de la decisión y, si hace falta refinar, qué debe corregir el especialista."
        )
    )


PROMPT_SUPERVISOR = SystemMessage(
    content=(
        "Sos el Supervisor de un orquestador jerárquico. Tu única función es "
        "evaluar el estado compartido y decidir el próximo nodo. No hagas el trabajo "
        "de los especialistas.\n\n"
        "RÚBRICA DE VALIDACIÓN:\n"
        "1) Investigación suficiente: contiene 3 a 5 hallazgos concretos, relevantes "
        "para la solicitud y sustentados en la herramienta de investigación. No debe "
        "inventar una evaluación económica detallada.\n"
        "2) Análisis suficiente: utiliza la investigación previa, incluye impacto "
        "operativo, al menos un cálculo numérico y una conclusión explícita sobre la "
        "viabilidad.\n"
        "3) Si una salida existe pero no cumple su criterio, devolvé al especialista "
        "correspondiente para que la refine e indicá claramente qué falta en 'razon'.\n"
        "4) Solo podés enviar a 'synthesizer' cuando investigación y análisis sean "
        "suficientes.\n"
        "5) Solo elegí 'FINISH' cuando ya exista una respuesta final.\n"
        "El flujo esperado normalmente es researcher -> analyst -> synthesizer, pero "
        "podés repetir researcher o analyst si su resultado no supera la rúbrica."
    )
)


def _resumen_estado(state: OrchestratorState) -> str:
    """Entrega al Supervisor solo el contexto necesario para validar y rutear."""

    return (
        f"SOLICITUD ORIGINAL:\n{state['user_request']}\n\n"
        f"INVESTIGACIÓN ACTUAL:\n{state.get('research_result') or '(todavía no existe)'}\n\n"
        f"ANÁLISIS ACTUAL:\n{state.get('analysis_result') or '(todavía no existe)'}\n\n"
        f"RESPUESTA FINAL:\n{state.get('final_answer') or '(todavía no existe)'}\n\n"
        f"DECISIONES PREVIAS DEL SUPERVISOR: {state.get('steps', 0)} de {MAX_STEPS}"
    )


def _asegurar_ruta_valida(
    decision: DecisionSupervisor, state: OrchestratorState
) -> tuple[str, str]:
    """Evita terminar o sintetizar si faltan prerrequisitos mínimos.

    La decisión sigue siendo del LLM Supervisor; esta capa solo impide rutas
    imposibles (por ejemplo FINISH sin respuesta final) y deja evidencia del ajuste.
    """

    elegida = decision.next_agent
    ajuste = ""

    # Si el propio Supervisor calificó un resultado como insuficiente, no
    # permitimos avanzar a una etapa posterior hasta refinarlo.
    if state.get("research_result") and not decision.research_sufficient and elegida != "researcher":
        elegida = "researcher"
        ajuste = " Se corrigió la ruta porque la investigación fue marcada como insuficiente."

    elif (
        state.get("analysis_result")
        and not decision.analysis_sufficient
        and elegida in {"synthesizer", "FINISH"}
    ):
        elegida = "analyst"
        ajuste = " Se corrigió la ruta porque el análisis fue marcado como insuficiente."

    elif elegida == "FINISH" and not state.get("final_answer"):
        if not state.get("research_result"):
            elegida = "researcher"
        elif not state.get("analysis_result"):
            elegida = "analyst"
        else:
            elegida = "synthesizer"
        ajuste = " Se corrigió la ruta porque FINISH requiere una respuesta final existente."

    elif elegida == "synthesizer":
        if not state.get("research_result"):
            elegida = "researcher"
            ajuste = " Se corrigió la ruta porque todavía falta investigación."
        elif not state.get("analysis_result"):
            elegida = "analyst"
            ajuste = " Se corrigió la ruta porque todavía falta análisis."

    elif elegida == "analyst" and not state.get("research_result"):
        elegida = "researcher"
        ajuste = " Se corrigió la ruta porque el analista necesita investigación previa."

    return elegida, ajuste


async def nodo_supervisor(state: OrchestratorState) -> dict:
    """Valida los aportes y decide dinámicamente qué especialista interviene."""

    steps = state.get("steps", 0)

    if state.get("final_answer"):
        return {
            "next_agent": "FINISH",
            "task_completed": True,
            "supervisor_feedback": "La síntesis final ya existe; el flujo puede terminar.",
            "validation_notes": [
                "Supervisor: la respuesta final ya existe y se valida el cierre del flujo."
            ],
        }

    if steps >= MAX_STEPS:
        # Si ya hay material de ambos especialistas, permitimos una síntesis final
        # de emergencia. Si falta uno, terminamos como incompleto en vez de fingir éxito.
        if state.get("research_result") and state.get("analysis_result"):
            return {
                "next_agent": "synthesizer",
                "task_completed": False,
                "supervisor_feedback": (
                    "Se alcanzó MAX_STEPS. Generar una síntesis final con la mejor evidencia disponible."
                ),
                "validation_notes": [
                    f"Supervisor: se alcanzó MAX_STEPS={MAX_STEPS}; se fuerza síntesis final."
                ],
            }
        return {
            "next_agent": "FINISH",
            "task_completed": False,
            "supervisor_feedback": "No fue posible completar los insumos antes del límite de pasos.",
            "validation_notes": [
                f"Supervisor: se alcanzó MAX_STEPS={MAX_STEPS} sin insumos suficientes; flujo incompleto."
            ],
        }

    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0).with_structured_output(
        DecisionSupervisor
    )
    decision: DecisionSupervisor = await modelo.ainvoke(
        [PROMPT_SUPERVISOR, HumanMessage(content=_resumen_estado(state))]
    )

    next_agent, ajuste = _asegurar_ruta_valida(decision, state)
    nota = (
        f"Supervisor (decisión {steps + 1}): next={next_agent}; "
        f"research_ok={decision.research_sufficient}; "
        f"analysis_ok={decision.analysis_sufficient}. {decision.razon}{ajuste}"
    )

    return {
        "next_agent": next_agent,
        "steps": steps + 1,
        "task_completed": False,
        "supervisor_feedback": decision.razon,
        "validation_notes": [nota],
    }


def _enrutar_desde_supervisor(state: OrchestratorState) -> str:
    return state["next_agent"]


async def nodo_researcher(state: OrchestratorState) -> dict:
    """Ejecuta investigación y conserva su aporte en el estado compartido."""

    agente = crear_agente_investigador()
    feedback = state.get("supervisor_feedback") or "Primera intervención; no hay correcciones previas."
    mensaje = (
        f"Solicitud original:\n{state['user_request']}\n\n"
        f"Feedback del Supervisor:\n{feedback}"
    )
    resultado = await agente.ainvoke({"messages": [HumanMessage(content=mensaje)]})
    respuesta = resultado["messages"][-1].content

    return {
        "research_result": respuesta,
        "contributions": [{"agente": "researcher", "resultado": respuesta}],
        "messages": [AIMessage(content=respuesta, name="researcher")],
    }


async def nodo_analyst(state: OrchestratorState) -> dict:
    """Analiza los hallazgos del investigador con herramientas de cómputo."""

    agente = crear_agente_analista()
    feedback = state.get("supervisor_feedback") or "Primera intervención; no hay correcciones previas."
    contexto = (
        f"Solicitud original:\n{state['user_request']}\n\n"
        f"Investigación disponible:\n{state.get('research_result') or '(sin investigación)'}\n\n"
        f"Feedback del Supervisor:\n{feedback}"
    )
    resultado = await agente.ainvoke({"messages": [HumanMessage(content=contexto)]})
    respuesta = resultado["messages"][-1].content

    return {
        "analysis_result": respuesta,
        "contributions": [{"agente": "analyst", "resultado": respuesta}],
        "messages": [AIMessage(content=respuesta, name="analyst")],
    }


async def nodo_synthesizer(state: OrchestratorState) -> dict:
    """Integra investigación y análisis, resolviendo posibles conflictos."""

    if not state.get("research_result") or not state.get("analysis_result"):
        raise ValueError("El sintetizador requiere investigación y análisis previos.")

    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    prompt = SystemMessage(
        content=(
            "Sos el sintetizador final. Integrá investigación y análisis en una "
            "recomendación concreta: conviene / conviene con reservas / no conviene. "
            "Si los agentes discrepan, priorizá la evidencia cuantitativa y operativa "
            "del analista, explicando brevemente el conflicto. No inventes cifras ni hechos nuevos. "
            "Toda cifra proveniente del analista (horas, valor hora, costo, ahorro, "
            "diferencia) debe presentarse explícitamente como SUPUESTO DEL ESCENARIO "
            "DEMO, nunca como dato real del negocio. "
            "Respondé en español en 6 a 8 líneas como máximo."
        )
    )
    contexto = HumanMessage(
        content=(
            f"Solicitud original:\n{state['user_request']}\n\n"
            f"Investigación:\n{state['research_result']}\n\n"
            f"Análisis:\n{state['analysis_result']}"
        )
    )
    respuesta = await modelo.ainvoke([prompt, contexto])

    return {
        "final_answer": respuesta.content,
        "task_completed": True,
        "contributions": [{"agente": "synthesizer", "resultado": respuesta.content}],
        "messages": [AIMessage(content=respuesta.content, name="synthesizer")],
    }


def construir_grafo(checkpointer=None) -> CompiledStateGraph:
    """Construye la topología jerárquica con Supervisor central."""

    grafo = StateGraph(OrchestratorState)
    grafo.add_node("approval_gate", nodo_approval_gate)
    grafo.add_node("supervisor", nodo_supervisor)
    grafo.add_node("researcher", nodo_researcher)
    grafo.add_node("analyst", nodo_analyst)
    grafo.add_node("synthesizer", nodo_synthesizer)

    grafo.add_edge(START, "approval_gate")
    grafo.add_conditional_edges(
        "approval_gate",
        route_after_gate,
        {"supervisor": "supervisor", "__end__": END},
    )
    grafo.add_conditional_edges(
        "supervisor",
        _enrutar_desde_supervisor,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "synthesizer": "synthesizer",
            "FINISH": END,
        },
    )

    grafo.add_edge("researcher", "supervisor")
    grafo.add_edge("analyst", "supervisor")
    grafo.add_edge("synthesizer", "supervisor")

    return grafo.compile(checkpointer=checkpointer)
