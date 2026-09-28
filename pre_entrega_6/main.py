"""Demo de la Pre-entrega 6: orquestador multi-agente jerárquico con LangGraph.

Ejecutar desde ESTA carpeta (no desde la raíz del repo):

    cd pre_entrega_6
    pip install -r requirements.txt
    python main.py

Corre una única consulta de punta a punta y va mostrando, en orden, la
intervención de cada agente (researcher -> analyst -> synthesizer),
coordinada en todo momento por el supervisor, hasta cerrar con
`task_completed = True`.
"""
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph import MAX_STEPS, construir_grafo

# Mismo criterio que pre_entrega_5: load_dotenv() busca el .env subiendo
# desde el directorio de trabajo actual, así que encuentra el .env de la
# raíz del repo aunque este script se corra parado en pre_entrega_6/.
load_dotenv()

CONSULTA_DEMO = (
    "Necesito evaluar si tiene sentido implementar un sistema con IA para "
    "un corralón. Quiero que investigues beneficios posibles, analices "
    "impacto operativo y cierres con una recomendación concreta."
)


def _validar_configuracion() -> None:
    """Corta con un mensaje claro si falta la API Key, antes de armar el grafo."""
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "Falta la variable de entorno OPENAI_API_KEY.\n"
            "Agregala al archivo .env de la raíz del repo (el mismo que "
            "usan las otras pre-entregas). Si querés usar un modelo "
            "distinto a gpt-4o-mini, agregá también MODEL_NAME."
        )


def _imprimir_contribuciones(contribuciones: list[dict]) -> None:
    print("\n--- CONTRIBUCIONES GUARDADAS POR CADA AGENTE ---")
    for i, aporte in enumerate(contribuciones, start=1):
        print(f"\n[{i}] Agente: {aporte['agente']}")
        print(aporte["resultado"])


def main() -> None:
    print("=== PRE-ENTREGA 6: ORQUESTADOR MULTI-AGENTE (LANGGRAPH) ===")

    try:
        _validar_configuracion()
    except ValueError as error:
        print(f"\nError de configuración: {error}")
        return

    grafo = construir_grafo()

    print(f"\nSolicitud original del usuario:\n{CONSULTA_DEMO}")

    estado_inicial = {
        "messages": [HumanMessage(content=CONSULTA_DEMO)],
        "user_request": CONSULTA_DEMO,
        "next_agent": "researcher",
        "research_result": None,
        "analysis_result": None,
        "final_answer": None,
        "contributions": [],
        "steps": 0,
        "task_completed": False,
        "validation_notes": [],
    }

    # recursion_limit es la red de seguridad de LangGraph (cuenta pasos de
    # NODO, no decisiones del supervisor): se deja generosa pero finita.
    # La protección real contra loops infinitos es MAX_STEPS, ya aplicada
    # dentro de graph.nodo_supervisor.
    resultado = grafo.invoke(estado_inicial, config={"recursion_limit": 25})

    print("\n--- INTERVENCIÓN DEL AGENTE INVESTIGADOR ---")
    print(resultado["research_result"])

    print("\n--- INTERVENCIÓN DEL AGENTE ANALISTA ---")
    print(resultado["analysis_result"])

    print("\n--- SÍNTESIS FINAL ---")
    print(resultado["final_answer"])

    _imprimir_contribuciones(resultado["contributions"])

    print("\n--- TRAZA DE DECISIONES DEL SUPERVISOR ---")
    for nota in resultado["validation_notes"]:
        print(f"- {nota}")

    print(
        f"\n[Flujo terminado sin loop infinito: task_completed={resultado['task_completed']}, "
        f"decisiones del supervisor={resultado['steps']} (tope configurado: {MAX_STEPS})]"
    )


if __name__ == "__main__":
    # La consola de Windows no siempre usa UTF-8 por default, y esta demo
    # imprime texto con tildes y "ñ". Sin esto, se ve con caracteres
    # corridos aunque los datos estén bien (mismo ajuste que pre_entrega_5).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    main()
