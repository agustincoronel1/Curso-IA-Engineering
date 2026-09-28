"""Agente especialista de investigación.

Se arma con `create_react_agent` (LangGraph prebuilt), que ya resuelve el
ciclo ReAct completo (llm -> tools -> llm) como un sub-grafo propio: no hace
falta escribir a mano el nodo del modelo, el `ToolNode` ni la arista
condicional, como sí se hizo en `pre_entrega_5`.

Su única herramienta es `simulated_research_search`, que NO llama a ningún
servicio externo (la consigna pide evitar Tavily u otra API de búsqueda):
simula lo que devolvería una búsqueda web o una consulta a una Vector DB,
filtrando una base de conocimiento fija embebida en este archivo por
palabras clave presentes en la consulta.
"""
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Busca el .env subiendo desde el directorio de trabajo actual. Si esta
# entrega se corre con `cd pre_entrega_6 && python main.py` (como pide la
# consigna), la búsqueda sube un nivel y encuentra el .env de la raíz del
# repo, el mismo que ya usan pre_entrega_1/3/4/5 (misma OPENAI_API_KEY).
load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Base de conocimiento fija que simula los resultados de una búsqueda
# externa o de una Vector DB. Cada entrada tiene "claves" (palabras que
# disparan la coincidencia) y un resumen ya redactado, para que la tool no
# tenga que generar texto: solo filtra y devuelve.
_BASE_CONOCIMIENTO = [
    {
        "claves": ["corralon", "corralón", "material", "construccion", "construcción", "ferreteria", "ferretería"],
        "titulo": "IA en corralones y comercios de materiales de construcción",
        "resumen": (
            "Corralones que adoptaron chatbots de atención y cotizadores "
            "automáticos reportan menos tiempo de espera para cotizar "
            "pedidos grandes (áridos, cemento, hierro) y menos errores de "
            "stock, porque el asistente consulta el inventario en tiempo "
            "real en vez de que un vendedor calcule a mano."
        ),
    },
    {
        "claves": ["atencion", "atención", "cliente", "chatbot", "whatsapp"],
        "titulo": "Automatización de atención al cliente",
        "resumen": (
            "Un asistente conversacional puede resolver consultas "
            "repetitivas (horarios, precios, disponibilidad, seguimiento de "
            "pedidos) las 24 horas, liberando al personal de mostrador para "
            "atender casos que sí requieren asesoramiento humano."
        ),
    },
    {
        "claves": ["stock", "inventario", "prediccion", "predicción", "demanda"],
        "titulo": "Predicción de demanda y gestión de stock",
        "resumen": (
            "Modelos simples de predicción de demanda, entrenados con el "
            "historial de ventas, ayudan a anticipar quiebres de stock en "
            "productos de alta rotación (cemento, arena) y a planificar "
            "mejor las compras a proveedores."
        ),
    },
    {
        "claves": ["costo", "inversion", "inversión", "implementacion", "implementación", "pyme"],
        "titulo": "Costo de implementación en pymes",
        "resumen": (
            "Para negocios chicos y medianos, la vía más económica suele "
            "ser integrar servicios de IA ya existentes (chatbots, "
            "cotizadores) sobre la infraestructura actual (WhatsApp "
            "Business, planilla de stock), en vez de desarrollar un sistema "
            "propio desde cero."
        ),
    },
]


@tool
def simulated_research_search(query: str) -> dict:
    """Simula una búsqueda externa (o una consulta a una Vector DB) sobre IA aplicada a negocios.

    No llama a ningún servicio real de internet: devuelve una base de
    conocimiento fija, embebida en este archivo, filtrada por palabras
    clave presentes en `query`. Reemplaza a una tool real de búsqueda (por
    ejemplo Tavily) para esta entrega, que evita dependencias externas de
    red.

    Args:
        query: Tema o pregunta a investigar (por ejemplo, "beneficios de IA
            para un corralón" o "automatización de atención al cliente").

    Returns:
        {"query": ..., "fuentes": [{"titulo": ..., "resumen": ...}, ...]}
        Si ninguna palabra clave coincide, devuelve la base completa (mejor
        pasar información de más que dejar al agente sin nada para razonar).
    """
    query_normalizada = query.lower()

    coincidencias = [
        {"titulo": item["titulo"], "resumen": item["resumen"]}
        for item in _BASE_CONOCIMIENTO
        if any(clave in query_normalizada for clave in item["claves"])
    ]

    if not coincidencias:
        coincidencias = [
            {"titulo": item["titulo"], "resumen": item["resumen"]} for item in _BASE_CONOCIMIENTO
        ]

    return {"query": query, "fuentes": coincidencias}


PROMPT_INVESTIGADOR = (
    "Sos un agente de investigación. Tu único trabajo es usar la "
    "herramienta simulated_research_search (al menos una vez) para reunir "
    "información relevante sobre la consulta del usuario, y después "
    "resumir en 3 a 5 bullets los hallazgos más relevantes para decidir si "
    "conviene implementar IA en el negocio descripto. No opines sobre "
    "viabilidad económica ni operativa: eso lo hace otro agente más "
    "adelante. Respondé siempre en español."
)


def crear_agente_investigador():
    """Arma el sub-grafo ReAct del agente investigador.

    Se crea un `ChatOpenAI` nuevo en cada llamada (objeto liviano, no abre
    conexión hasta invocarse) para no depender de un modelo global mutable,
    mismo criterio que `pre_entrega_5/agent.py`.
    """
    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    return create_react_agent(
        model=modelo,
        tools=[simulated_research_search],
        prompt=PROMPT_INVESTIGADOR,
        name="researcher",
    )
