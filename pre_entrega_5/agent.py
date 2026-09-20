"""Construccion del grafo del agente (StateGraph + ciclo ReAct).

Flujo del grafo:

    START -> agent -> (tools_condition) -> tools -> agent -> ... -> END

- "agent": un nodo que le pasa el historial de mensajes al LLM (con las
  tools "bindeadas") y devuelve su respuesta. El LLM decide solo, mirando
  las descripciones de las tools, si responde directo o si pide ejecutar
  una herramienta.
- "tools": `ToolNode`, provisto por LangGraph. Lee el/los tool_call(s) que
  generic el LLM en el ultimo mensaje, ejecuta la funcion Python real
  correspondiente y agrega el resultado al historial como `ToolMessage`.
- La arista condicional (`tools_condition`) mira si el ultimo mensaje del
  LLM trae tool_calls: si trae, va a "tools"; si no, corta a END.
- La arista "tools" -> "agent" es la que cierra el ciclo ReAct: despues de
  ejecutar una herramienta, SIEMPRE se vuelve al LLM para que interprete el
  resultado y decida el siguiente paso (otra tool, o la respuesta final).

En ningun lado de este archivo hay un `if pregunta contiene ...`: la unica
decision sobre que herramienta usar la toma el LLM via tool calling.
"""
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from pre_entrega_5 import config
from pre_entrega_5.state import AgentState
from pre_entrega_5.tools import HERRAMIENTAS

# Mensaje de sistema: fija el rol del agente y dos reglas de seguridad
# (no inventar datos, pedir aclaracion ante ambiguedad). No le pedimos en
# ningun momento que "explique su razonamiento paso a paso": la traza que
# se guarda en trace.py se arma solo con eventos observables (mensajes,
# tool calls y resultados), nunca con el pensamiento interno del modelo.
PROMPT_SISTEMA = SystemMessage(
    content=(
        "Sos un asistente que responde preguntas sobre clientes y sus pedidos "
        "de una tienda. Solo conoces los datos que te devuelven las "
        "herramientas disponibles: nunca inventes un cliente_id, una cantidad "
        "de pedidos o un monto que no haya salido de una herramienta. "
        "Si una herramienta indica que no encontro algo, o que el nombre es "
        "ambiguo, decilo con claridad y pedile al usuario que aclare en vez "
        "de adivinar. Respondé siempre en español, de forma breve y concreta."
    )
)


def _crear_modelo_con_tools() -> ChatOpenAI:
    """Arma el LLM y le "bindea" las herramientas disponibles.

    `bind_tools` no ejecuta nada: solo le agrega al LLM las definiciones de
    las tools (nombre, descripcion, parametros) para que, en cada llamada,
    el modelo pueda decidir devolver una respuesta normal o un tool_call.
    """
    modelo = ChatOpenAI(
        model=config.MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
        temperature=0,
    )
    return modelo.bind_tools(HERRAMIENTAS)


async def call_model(state: AgentState) -> dict:
    """Nodo "agent": le pasa el historial al LLM y devuelve su respuesta.

    Se crea el modelo en cada llamada porque es un objeto liviano (no abre
    conexiones de red hasta invocarlo) y asi este archivo no depende de un
    estado global mutable. Se usa `ainvoke` (version async) porque todo el
    grafo se corre con `graph.ainvoke(...)` desde main.py.
    """
    modelo_con_tools = _crear_modelo_con_tools()
    mensajes = [PROMPT_SISTEMA, *state["messages"]]
    respuesta = await modelo_con_tools.ainvoke(mensajes)
    return {"messages": [respuesta]}


def construir_agente(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Arma el StateGraph completo y lo compila con el checkpointer de SQLite.

    El checkpointer es lo que le da al grafo memoria persistente por
    thread_id: en cada paso, LangGraph guarda el estado (los mensajes
    acumulados) asociado al thread_id de la ejecucion, y lo recupera solo si
    se vuelve a invocar con el mismo thread_id.
    """
    grafo = StateGraph(AgentState)

    grafo.add_node("agent", call_model)
    grafo.add_node("tools", ToolNode(HERRAMIENTAS))

    grafo.add_edge(START, "agent")
    # tools_condition ya devuelve "tools" o END segun si el ultimo mensaje
    # del LLM trae tool_calls. El mapeo se lo dejamos explicito igual, para
    # que las dos ramas del grafo queden a la vista en este archivo.
    grafo.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    # Esta es la arista que cierra el ciclo ReAct: tool -> agent -> tool -> ...
    grafo.add_edge("tools", "agent")

    return grafo.compile(checkpointer=checkpointer)
