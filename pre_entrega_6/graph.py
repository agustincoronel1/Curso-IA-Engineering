"""Construcción del grafo del orquestador: topología jerárquica con supervisor.

Flujo del grafo:

    START -> supervisor -> (conditional edge) -> researcher/analyst/synthesizer/END
    researcher -> supervisor
    analyst -> supervisor
    synthesizer -> supervisor

El supervisor es el ÚNICO nodo que decide a dónde va el flujo (topología
jerárquica: los especialistas nunca se llaman entre sí ni deciden el
siguiente paso, siempre vuelven al supervisor). Esa decisión se toma con
"structured output": el LLM no devuelve texto libre, sino una instancia de
`DecisionSupervisor` (Pydantic), cuyo campo `next_agent` es un `Literal`
con los únicos cuatro valores válidos. Eso evita tener que parsear texto
para saber a qué nodo ir.

Cómo se evita el loop infinito:
1. Si ya existe `final_answer` en el estado, el supervisor corta a "FINISH"
   directo, sin ni siquiera llamar al LLM.
2. Si `steps` (cantidad de veces que el supervisor ya decidió) llega a
   `MAX_STEPS`, se fuerza "FINISH" sin importar lo que el LLM hubiera
   decidido.
3. Además, `construir_grafo` no fija un `recursion_limit`: quien invoca el
   grafo (ver `main.py`) le pasa uno generoso pero finito, como red de
   seguridad adicional de LangGraph por si el punto 1 y 2 fallaran.
"""
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from agents.analyst_agent import crear_agente_analista
from agents.research_agent import crear_agente_investigador
from state import OrchestratorState

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Tope de decisiones del supervisor para una misma consulta. El flujo
# "feliz" (researcher -> analyst -> synthesizer -> FINISH) necesita 4
# decisiones del supervisor; se deja margen para que el supervisor pueda,
# por ejemplo, volver a pedir análisis una vez más si lo considera
# necesario, sin arriesgarse a un loop infinito.
MAX_STEPS = 6


class DecisionSupervisor(BaseModel):
    """Salida estructurada que el supervisor produce en cada una de sus vueltas."""

    next_agent: Literal["researcher", "analyst", "synthesizer", "FINISH"] = Field(
        description=(
            "Próximo nodo a ejecutar. 'researcher' si todavía falta "
            "investigación. 'analyst' si ya hay investigación pero falta "
            "análisis de impacto/viabilidad. 'synthesizer' si ya hay "
            "investigación Y análisis pero todavía no existe una respuesta "
            "final. 'FINISH' si la respuesta final ya está lista."
        )
    )
    razon: str = Field(
        description="Explicación breve (una oración, en español) de por qué se eligió ese próximo paso."
    )


PROMPT_SUPERVISOR = SystemMessage(
    content=(
        "Sos el supervisor de un equipo de agentes que evalúan si conviene "
        "implementar un sistema de IA en un negocio. Coordinás tres "
        "agentes especialistas: 'researcher' (investiga beneficios "
        "posibles de la IA para ese tipo de negocio), 'analyst' (analiza "
        "impacto operativo y viabilidad económica) y 'synthesizer' "
        "(redacta la recomendación final integrando lo anterior). Regla de "
        "orden: primero necesitás investigación, después análisis, y "
        "recién ahí podés pasar a síntesis. No repitas un agente que ya "
        "generó su resultado salvo que consideres que su aporte fue "
        "insuficiente para tomar una decisión. Cuando ya exista una "
        "respuesta final, elegí 'FINISH'."
    )
)


def _resumen_estado(state: OrchestratorState) -> str:
    """Resume el estado actual en texto plano, para que el supervisor decida con contexto."""
    return (
        f"Solicitud del usuario: {state['user_request']}\n"
        f"¿Hay resultado de investigación?: {'si' if state.get('research_result') else 'no'}\n"
        f"¿Hay resultado de análisis?: {'si' if state.get('analysis_result') else 'no'}\n"
        f"¿Hay respuesta final?: {'si' if state.get('final_answer') else 'no'}\n"
        f"Decisiones del supervisor tomadas hasta ahora: {state.get('steps', 0)} (tope: {MAX_STEPS})"
    )


def nodo_supervisor(state: OrchestratorState) -> dict:
    """Nodo router: decide, con salida estructurada, cuál es el próximo agente.

    Este nodo NUNCA hace el trabajo de un especialista: solo lee el estado
    acumulado y decide a dónde mandar el flujo. Es lo que hace que la
    topología sea jerárquica en vez de un grafo donde cualquier nodo puede
    llamar a cualquier otro.
    """
    steps = state.get("steps", 0)

    if state.get("final_answer"):
        return {"next_agent": "FINISH", "task_completed": True}

    if steps >= MAX_STEPS:
        return {
            "next_agent": "FINISH",
            "task_completed": True,
            "validation_notes": [
                f"Se alcanzó el tope de {MAX_STEPS} decisiones del supervisor: se cierra el flujo sin más pasos."
            ],
        }

    modelo_estructurado = ChatOpenAI(model=MODEL_NAME, temperature=0).with_structured_output(
        DecisionSupervisor
    )
    decision: DecisionSupervisor = modelo_estructurado.invoke(
        [PROMPT_SUPERVISOR, HumanMessage(content=_resumen_estado(state))]
    )

    return {
        "next_agent": decision.next_agent,
        "steps": steps + 1,
        "validation_notes": [f"Supervisor (decisión {steps + 1}): {decision.razon}"],
    }


def _enrutar_desde_supervisor(state: OrchestratorState) -> str:
    """Traduce el campo next_agent del estado a una clave del mapeo de add_conditional_edges."""
    return state["next_agent"]


def nodo_researcher(state: OrchestratorState) -> dict:
    """Ejecuta el agente investigador y guarda su resultado en el estado."""
    agente = crear_agente_investigador()
    resultado = agente.invoke({"messages": [HumanMessage(content=state["user_request"])]})
    respuesta = resultado["messages"][-1].content

    return {
        "research_result": respuesta,
        "contributions": [{"agente": "researcher", "resultado": respuesta}],
        "messages": [AIMessage(content=respuesta, name="researcher")],
    }


def nodo_analyst(state: OrchestratorState) -> dict:
    """Ejecuta el agente analista, pasándole la investigación previa como contexto."""
    agente = crear_agente_analista()
    contexto = (
        f"Solicitud original del usuario: {state['user_request']}\n\n"
        f"Investigación disponible:\n{state.get('research_result') or '(sin investigación previa)'}"
    )
    resultado = agente.invoke({"messages": [HumanMessage(content=contexto)]})
    respuesta = resultado["messages"][-1].content

    return {
        "analysis_result": respuesta,
        "contributions": [{"agente": "analyst", "resultado": respuesta}],
        "messages": [AIMessage(content=respuesta, name="analyst")],
    }


def nodo_synthesizer(state: OrchestratorState) -> dict:
    """Integra investigación + análisis en una recomendación final concreta.

    Si detecta que la investigación pinta un panorama optimista pero el
    análisis dice que el caso de negocio no cierra (o viceversa), se le
    pide explícitamente que priorice el análisis económico/operativo y
    aclare la contradicción en vez de promediar ambos discursos sin
    comentario. Así se resuelve un posible conflicto entre agentes.
    """
    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    prompt = SystemMessage(
        content=(
            "Sos el agente sintetizador. Integrá la investigación y el "
            "análisis en una recomendación final clara y concreta "
            "(conviene / conviene con reservas / no conviene), en "
            "español, en no más de 6 a 8 líneas. Si detectás una "
            "contradicción entre la investigación (beneficios posibles) y "
            "el análisis (impacto operativo y viabilidad económica), "
            "priorizá el análisis por sobre el optimismo de la "
            "investigación, y aclarálo explícitamente en la respuesta."
        )
    )
    contexto = HumanMessage(
        content=(
            f"Solicitud original: {state['user_request']}\n\n"
            f"Investigación:\n{state.get('research_result') or '(sin datos)'}\n\n"
            f"Análisis:\n{state.get('analysis_result') or '(sin datos)'}"
        )
    )
    respuesta = modelo.invoke([prompt, contexto])

    return {
        "final_answer": respuesta.content,
        "task_completed": True,
        "contributions": [{"agente": "synthesizer", "resultado": respuesta.content}],
        "messages": [AIMessage(content=respuesta.content, name="synthesizer")],
    }


def construir_grafo() -> CompiledStateGraph:
    """Arma y compila el StateGraph jerárquico completo."""
    grafo = StateGraph(OrchestratorState)

    grafo.add_node("supervisor", nodo_supervisor)
    grafo.add_node("researcher", nodo_researcher)
    grafo.add_node("analyst", nodo_analyst)
    grafo.add_node("synthesizer", nodo_synthesizer)

    grafo.add_edge(START, "supervisor")

    # La única arista condicional del grafo: todo el ruteo pasa por acá.
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

    # Los tres especialistas siempre vuelven al supervisor: nunca se llaman
    # entre sí ni terminan el grafo por su cuenta (topología jerárquica).
    grafo.add_edge("researcher", "supervisor")
    grafo.add_edge("analyst", "supervisor")
    grafo.add_edge("synthesizer", "supervisor")

    return grafo.compile()
