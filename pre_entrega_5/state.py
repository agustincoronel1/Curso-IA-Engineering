"""Estado del grafo.

LangGraph ya trae `MessagesState`, un TypedDict con un unico campo:

    messages: Annotated[list[AnyMessage], add_messages]

El `Annotated[..., add_messages]` es lo importante: le dice a LangGraph que,
cuando un nodo devuelve `{"messages": [nuevo_mensaje]}`, ese mensaje se
AGREGUE a la lista existente (reducer), en vez de reemplazarla entera. Por
eso ningun nodo de agent.py reescribe `state["messages"]` a mano: solo
devuelve el mensaje nuevo y LangGraph se encarga de acumular el historial.

Esta entrega no necesita ningun campo extra en el estado (no hay, por
ejemplo, un contador de reintentos ni banderas propias): toda la logica de
"a que cliente se refiere" o "cuantas herramientas hacen falta" vive en el
propio historial de mensajes, que el LLM relee en cada vuelta del ciclo. Por
eso alcanza con reusar MessagesState tal cual, en vez de definir un
TypedDict propio.
"""
from langgraph.graph import MessagesState

# Alias con nombre propio del proyecto, para que agent.py no dependa
# directamente del nombre "MessagesState" de LangGraph en todos lados.
AgentState = MessagesState
