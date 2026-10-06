"""Agente especialista de investigación."""

import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Base de conocimiento local usada como búsqueda simulada. La consigna
# permite Tavily o una búsqueda simulada sobre una fuente propia; elegimos
# esta segunda opción para que la demo sea reproducible sin otra API.
_BASE_CONOCIMIENTO = [
    {
        "claves": [
            "corralon",
            "corralón",
            "material",
            "construccion",
            "construcción",
            "ferreteria",
            "ferretería",
        ],
        "titulo": "Oportunidades de IA en un corralón",
        "resumen": (
            "La automatización puede reducir tareas repetitivas de cotización, "
            "consulta de precios, seguimiento de presupuestos y consulta de stock."
        ),
    },
    {
        "claves": ["atencion", "atención", "cliente", "chatbot", "whatsapp"],
        "titulo": "Atención al cliente y seguimiento",
        "resumen": (
            "Un asistente puede resolver consultas frecuentes y ayudar a dar "
            "seguimiento a presupuestos, liberando tiempo del personal para casos "
            "que requieren intervención humana."
        ),
    },
    {
        "claves": ["stock", "inventario", "prediccion", "predicción", "demanda"],
        "titulo": "Stock e inventario",
        "resumen": (
            "El historial de ventas y movimientos puede utilizarse para detectar "
            "patrones, alertar sobre faltantes y apoyar la planificación de compras."
        ),
    },
    {
        "claves": [
            "costo",
            "inversion",
            "inversión",
            "implementacion",
            "implementación",
            "pyme",
        ],
        "titulo": "Implementación gradual en una pyme",
        "resumen": (
            "Una adopción incremental permite validar primero los casos de uso con "
            "mayor retorno antes de ampliar la solución a procesos más complejos."
        ),
    },
]


@tool
def simulated_research_search(query: str) -> dict:
    """Busca información en una base local que simula una fuente externa/vectorial.

    Args:
        query: Tema o pregunta a investigar.

    Returns:
        Diccionario con la consulta y los resultados simulados más relevantes.
    """

    query_normalizada = query.lower()
    coincidencias = [
        {"titulo": item["titulo"], "resumen": item["resumen"]}
        for item in _BASE_CONOCIMIENTO
        if any(clave in query_normalizada for clave in item["claves"])
    ]

    if not coincidencias:
        coincidencias = [
            {"titulo": item["titulo"], "resumen": item["resumen"]}
            for item in _BASE_CONOCIMIENTO
        ]

    return {"query": query, "fuentes_simuladas": coincidencias}


PROMPT_INVESTIGADOR = (
    "Sos un agente especialista en investigación. Debés usar obligatoriamente "
    "simulated_research_search al menos una vez. Después resumí entre 3 y 5 "
    "hallazgos concretos y relevantes para la solicitud. No evalúes todavía la "
    "viabilidad económica: esa tarea pertenece al agente analista. Si recibís "
    "feedback del Supervisor, corregí específicamente ese punto. Respondé en español."
)


def crear_agente_investigador():
    """Construye el subgrafo ReAct del especialista de investigación."""

    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    return create_react_agent(
        model=modelo,
        tools=[simulated_research_search],
        prompt=PROMPT_INVESTIGADOR,
        name="researcher",
    )
