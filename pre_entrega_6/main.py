"""Demo ejecutable de la Pre-entrega 6."""

import argparse
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph import MAX_STEPS, construir_grafo

load_dotenv()

CONSULTA_DEMO = (
    "Necesito evaluar si tiene sentido implementar un sistema con IA para un corralón. "
    "Quiero que investigues beneficios posibles, analices impacto operativo y cierres "
    "con una recomendación concreta."
)


def _validar_configuracion() -> None:
    if sys.version_info < (3, 12):
        raise RuntimeError("Esta entrega requiere Python 3.12 o superior.")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "Falta OPENAI_API_KEY. Copiá .env.example como .env y completá tu clave."
        )


def _estado_inicial(consulta: str) -> dict:
    return {
        "messages": [HumanMessage(content=consulta)],
        "user_request": consulta,
        "next_agent": "researcher",
        "research_result": None,
        "analysis_result": None,
        "final_answer": None,
        "supervisor_feedback": None,
        "contributions": [],
        "steps": 0,
        "task_completed": False,
        "validation_notes": [],
    }


def _imprimir_resultado(resultado: dict) -> None:
    print("\n--- INVESTIGACIÓN ---")
    print(resultado.get("research_result") or "(sin resultado)")

    print("\n--- ANÁLISIS / CÓMPUTO ---")
    print(resultado.get("analysis_result") or "(sin resultado)")

    print("\n--- SÍNTESIS FINAL ---")
    print(resultado.get("final_answer") or "(sin resultado)")

    print("\n--- CONTRIBUCIONES POR AGENTE ---")
    for i, aporte in enumerate(resultado.get("contributions", []), start=1):
        print(f"[{i}] {aporte['agente']}")

    print("\n--- VALIDACIÓN Y RUTEO DEL SUPERVISOR ---")
    for nota in resultado.get("validation_notes", []):
        print(f"- {nota}")

    print(
        f"\nEstado final: task_completed={resultado.get('task_completed')} | "
        f"decisiones={resultado.get('steps')} | MAX_STEPS={MAX_STEPS}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo del orquestador multi-agente")
    parser.add_argument(
        "--query",
        default=CONSULTA_DEMO,
        help="Consulta a resolver. Si se omite, se usa la consulta demo.",
    )
    args = parser.parse_args()

    print("=== PRE-ENTREGA 6: ORQUESTADOR MULTI-AGENTE ===")
    _validar_configuracion()

    grafo = construir_grafo()
    resultado = grafo.invoke(_estado_inicial(args.query), config={"recursion_limit": 25})
    _imprimir_resultado(resultado)

    if not resultado.get("task_completed") or not resultado.get("final_answer"):
        raise RuntimeError("El flujo terminó sin completar una síntesis final válida.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    main()
