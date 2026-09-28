"""Agente especialista de análisis/cómputo.

Igual que `research_agent.py`, se arma con `create_react_agent`. Tiene dos
herramientas de cálculo simple (sin llamadas externas):

- `estimate_automation_impact`: estima horas ahorradas por semana y nivel
  de impacto de automatizar un área del negocio.
- `validate_business_case`: valida si ese ahorro justifica el costo mensual
  estimado de la solución (caso de negocio).
"""
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Horas ahorradas por semana según volumen de operaciones declarado. Es una
# tabla fija y simple a propósito: el objetivo de esta tool es simular un
# cálculo de impacto operativo, no modelar con precisión un negocio real.
_HORAS_POR_VOLUMEN = {"bajo": 4, "medio": 10, "alto": 20}


@tool
def estimate_automation_impact(area: str, volumen_operaciones: str = "medio") -> dict:
    """Estima el impacto operativo de automatizar un área del negocio con IA.

    Simula un cálculo simple (sin llamar a ningún servicio externo) de
    horas ahorradas por semana y de nivel de impacto, a partir del área
    elegida y el volumen de operaciones declarado.

    Args:
        area: Área del negocio a automatizar (por ejemplo "atención al
            cliente", "cotización de pedidos", "gestión de stock").
        volumen_operaciones: "bajo", "medio" o "alto". Por default "medio".
            Si no coincide con ninguno de esos tres valores, se usa "medio".

    Returns:
        {"area": ..., "volumen_operaciones": ..., "horas_ahorradas_semana_estimadas": ...,
         "nivel_impacto": "bajo" | "medio" | "alto"}
    """
    horas = _HORAS_POR_VOLUMEN.get(volumen_operaciones.lower(), _HORAS_POR_VOLUMEN["medio"])

    if horas >= 15:
        nivel_impacto = "alto"
    elif horas >= 8:
        nivel_impacto = "medio"
    else:
        nivel_impacto = "bajo"

    return {
        "area": area,
        "volumen_operaciones": volumen_operaciones,
        "horas_ahorradas_semana_estimadas": horas,
        "nivel_impacto": nivel_impacto,
    }


@tool
def validate_business_case(
    costo_estimado_mensual: float,
    horas_ahorradas_semana: float,
    valor_hora: float = 3000,
) -> dict:
    """Valida si el caso de negocio de automatizar con IA cierra económicamente.

    Compara el costo mensual estimado de la solución contra el valor de las
    horas de trabajo humano que se ahorrarían por mes
    (horas_ahorradas_semana * 4 * valor_hora). No llama a ningún servicio
    externo: es un cálculo simple pensado para justificar una recomendación,
    no una proyección financiera real.

    Args:
        costo_estimado_mensual: Costo mensual estimado de implementar y
            mantener la solución de IA (misma moneda que valor_hora).
        horas_ahorradas_semana: Horas semanales que se ahorrarían, tal como
            las devuelve `estimate_automation_impact`.
        valor_hora: Costo por hora de trabajo humano evitado. Default 3000
            (valor de referencia en la misma moneda que costo_estimado_mensual).

    Returns:
        {"ahorro_mensual_estimado": ..., "costo_estimado_mensual": ...,
         "diferencia_mensual": ...,
         "recomendacion": "conviene" | "conviene con reservas" | "no conviene"}
    """
    ahorro_mensual = horas_ahorradas_semana * 4 * valor_hora
    diferencia = ahorro_mensual - costo_estimado_mensual

    if diferencia > costo_estimado_mensual:
        recomendacion = "conviene"
    elif diferencia > 0:
        recomendacion = "conviene con reservas"
    else:
        recomendacion = "no conviene"

    return {
        "ahorro_mensual_estimado": ahorro_mensual,
        "costo_estimado_mensual": costo_estimado_mensual,
        "diferencia_mensual": diferencia,
        "recomendacion": recomendacion,
    }


PROMPT_ANALISTA = (
    "Sos un agente de análisis. Recibís la solicitud del usuario y, si "
    "está disponible, la investigación previa de otro agente. Tu trabajo es "
    "usar estimate_automation_impact (elegí un área y un volumen de "
    "operaciones razonables según el contexto) y después "
    "validate_business_case (asumí un costo_estimado_mensual razonable "
    "para una pyme, por ejemplo entre 50000 y 150000, y usá las horas que "
    "te devolvió la tool anterior) para evaluar si el caso de negocio "
    "cierra. Cerrá con 3 a 5 bullets: impacto operativo estimado, y si el "
    "caso de negocio conviene, conviene con reservas o no conviene, con el "
    "número que lo justifica. Respondé siempre en español."
)


def crear_agente_analista():
    """Arma el sub-grafo ReAct del agente analista."""
    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    return create_react_agent(
        model=modelo,
        tools=[estimate_automation_impact, validate_business_case],
        prompt=PROMPT_ANALISTA,
        name="analyst",
    )
