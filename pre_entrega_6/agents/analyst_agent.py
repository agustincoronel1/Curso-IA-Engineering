"""Agente especialista de análisis/cómputo."""

import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Supuestos controlados del escenario demo (corralón). No provienen de datos
# reales: son supuestos explícitos y el LLM no puede modificarlos ni inventarlos.
_SUPUESTOS_ESCENARIO = {
    "volumen_operaciones": "medio",
    "horas_ahorradas_semana": 10,
    "valor_hora": 3000,
    "costo_estimado_mensual": 90000,
}


@tool
def estimate_automation_impact(area: str) -> dict:
    """Devuelve los supuestos del escenario demo y el impacto operativo estimado.

    Todos los valores numéricos provienen de supuestos definidos en código.
    """

    horas = _SUPUESTOS_ESCENARIO["horas_ahorradas_semana"]
    if horas >= 15:
        nivel_impacto = "alto"
    elif horas >= 8:
        nivel_impacto = "medio"
    else:
        nivel_impacto = "bajo"

    return {
        "area": area,
        "origen": "SUPUESTO del escenario demo (no son datos reales)",
        **_SUPUESTOS_ESCENARIO,
        "nivel_impacto": nivel_impacto,
    }


@tool
def validate_business_case() -> dict:
    """Valida el caso de negocio usando solo los supuestos del escenario demo."""

    horas = _SUPUESTOS_ESCENARIO["horas_ahorradas_semana"]
    valor_hora = _SUPUESTOS_ESCENARIO["valor_hora"]
    costo = _SUPUESTOS_ESCENARIO["costo_estimado_mensual"]

    ahorro_mensual = horas * 4 * valor_hora
    diferencia = ahorro_mensual - costo

    if diferencia > costo:
        recomendacion = "conviene"
    elif diferencia > 0:
        recomendacion = "conviene con reservas"
    else:
        recomendacion = "no conviene"

    return {
        "origen": "SUPUESTO del escenario demo (no son datos reales)",
        "horas_ahorradas_semana": horas,
        "valor_hora": valor_hora,
        "ahorro_mensual_estimado": ahorro_mensual,
        "costo_estimado_mensual": costo,
        "diferencia_mensual": diferencia,
        "recomendacion": recomendacion,
    }


PROMPT_ANALISTA = (
    "Sos un agente especialista en análisis/cómputo. Recibís la solicitud original, "
    "la investigación previa y, cuando corresponda, feedback del Supervisor. Usá "
    "obligatoriamente estimate_automation_impact y después validate_business_case. "
    "Usá EXCLUSIVAMENTE los números devueltos por esas tools (horas, valor_hora, costo, "
    "ahorro); no inventes ni estimes cifras propias. Indicá explícitamente que son "
    "supuestos del escenario demo. "
    "La respuesta debe incluir impacto operativo, al menos un cálculo numérico y una "
    "conclusión explícita: conviene / conviene con reservas / no conviene. Si el "
    "Supervisor pide refinamiento, corregí específicamente ese aspecto. Respondé en español."
)


def crear_agente_analista():
    """Construye el subgrafo ReAct del especialista de análisis."""

    modelo = ChatOpenAI(model=MODEL_NAME, temperature=0)
    return create_react_agent(
        model=modelo,
        tools=[estimate_automation_impact, validate_business_case],
        prompt=PROMPT_ANALISTA,
        name="analyst",
    )
