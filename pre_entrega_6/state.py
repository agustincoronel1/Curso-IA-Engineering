"""Estado compartido del orquestador multi-agente.

`OrchestratorState` extiende `MessagesState` (que ya trae el campo
`messages` con su reducer `add_messages`) y agrega los campos propios que
necesita esta entrega para coordinar al supervisor y a los agentes
especialistas.

Reducers usados:
- `contributions` y `validation_notes` usan `Annotated[list, operator.add]`:
  cada nodo devuelve solo SU aporte nuevo (una lista de un elemento) y
  LangGraph la concatena a la lista acumulada, en vez de pisarla. Así
  `contributions` termina con el aporte de researcher + analyst +
  synthesizer, en orden, sin que ningún nodo necesite leer y reescribir la
  lista completa.
- El resto de los campos (`user_request`, `next_agent`, `research_result`,
  `analysis_result`, `final_answer`, `steps`, `task_completed`) NO tiene
  reducer: cada nodo que los devuelve reemplaza el valor anterior. Es lo que
  se quiere para un contador (`steps`) o para un resultado que un solo nodo
  escribe una vez (`research_result`).
"""
import operator
from typing import Annotated, Literal, Optional

from langgraph.graph import MessagesState

# Nombres válidos de próximo nodo. "FINISH" no es un nodo real: es la señal
# que el supervisor usa para indicarle a la arista condicional que corte a
# END en vez de mandar a otro agente.
NextAgent = Literal["researcher", "analyst", "synthesizer", "FINISH"]


class OrchestratorState(MessagesState):
    # Consulta original del usuario, tal como llegó a main.py. Se guarda
    # aparte de `messages` para que cualquier nodo pueda leerla directo, sin
    # tener que buscar el primer HumanMessage del historial.
    user_request: str

    # Decisión más reciente del supervisor: a qué nodo mandar el flujo.
    next_agent: NextAgent

    # Resultados que va completando cada especialista. Empiezan en None y
    # se llenan una sola vez (researcher llena research_result, analyst
    # llena analysis_result, synthesizer llena final_answer).
    research_result: Optional[str]
    analysis_result: Optional[str]
    final_answer: Optional[str]

    # Bitácora de aportes: un item por cada vez que un agente (researcher,
    # analyst o synthesizer) termina su trabajo. Sirve para mostrar en
    # main.py, al final, qué generó cada agente, sin depender de leer el
    # historial completo de mensajes.
    contributions: Annotated[list[dict], operator.add]

    # Cuenta cuántas veces el supervisor ya tomó una decisión. Es el
    # mecanismo central para evitar loops infinitos: graph.py lo compara
    # contra MAX_STEPS y fuerza "FINISH" si se llega al tope.
    steps: int

    # Se pone en True recién cuando el flujo termina (ya sea porque
    # synthesizer generó una respuesta final, o porque se forzó el corte por
    # MAX_STEPS). main.py lo usa para confirmar que el grafo no quedó
    # colgado.
    task_completed: bool

    # Notas de validación/razonamiento que va dejando el supervisor en cada
    # paso (por qué eligió ese próximo agente), más cualquier aviso de corte
    # forzado por MAX_STEPS. Es la traza legible de las decisiones de
    # ruteo, separada de `contributions` (que son los aportes de contenido).
    validation_notes: Annotated[list[str], operator.add]
