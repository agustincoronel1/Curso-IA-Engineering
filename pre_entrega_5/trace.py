"""Traza ReAct: convierte el historial de mensajes en eventos observables.

El objetivo es poder mostrar, de forma legible, el ciclo
Agent -> Tool -> Agent -> Tool -> Agent que ocurrio durante una consulta.
La traza se arma SOLO con lo que ya es publico en el historial de mensajes
(pregunta del usuario, que tool se llamo con que argumentos, que devolvio, y
la respuesta final). En ningun momento se le pide al modelo que explique su
razonamiento interno, asi que no hay chain-of-thought en la traza: lo que se
guarda es el rastro de acciones, no los pensamientos privados del LLM.

Tampoco hay riesgo de filtrar API keys: los mensajes de LangChain nunca
contienen credenciales, solo texto de la conversacion y resultados de las
tools (que a su vez son datos de negocio, no configuracion).
"""
import json
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def construir_traza(mensajes: list[BaseMessage]) -> list[dict]:
    """Recorre el historial y devuelve una lista de eventos tipo:

        {"type": "user", "content": "..."}
        {"type": "tool_call", "tool": "...", "args": {...}}
        {"type": "tool_result", "tool": "...", "result": {...}}
        {"type": "assistant", "content": "..."}
    """
    eventos: list[dict] = []

    for mensaje in mensajes:
        if isinstance(mensaje, HumanMessage):
            eventos.append({"type": "user", "content": mensaje.content})

        elif isinstance(mensaje, AIMessage):
            if mensaje.tool_calls:
                for llamada in mensaje.tool_calls:
                    eventos.append(
                        {
                            "type": "tool_call",
                            "tool": llamada["name"],
                            "args": llamada["args"],
                        }
                    )
            elif mensaje.content:
                eventos.append({"type": "assistant", "content": mensaje.content})

        elif isinstance(mensaje, ToolMessage):
            eventos.append(
                {
                    "type": "tool_result",
                    "tool": mensaje.name,
                    "result": _parsear_resultado(mensaje.content),
                }
            )

        # Los SystemMessage (el prompt de sistema de agent.py) no forman
        # parte de la conversacion observable con el usuario: se omiten.

    return eventos


def _parsear_resultado(contenido) -> object:
    """El ToolNode serializa el dict que devuelve la tool como texto JSON.

    Acá se intenta recuperar el dict original para que la traza quede
    legible (en vez de una string JSON escapada). Si por algun motivo no es
    JSON valido, se deja el contenido tal cual vino.
    """
    if isinstance(contenido, str):
        try:
            return json.loads(contenido)
        except json.JSONDecodeError:
            return contenido
    return contenido


def guardar_traza(traza: list[dict], ruta: Path) -> None:
    """Guarda la traza como JSON legible (indentado, UTF-8, con acentos)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(traza, archivo, ensure_ascii=False, indent=2)
