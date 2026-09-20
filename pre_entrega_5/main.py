"""Demo de la Pre-entrega 5: agente ReAct con LangGraph + memoria en SQLite.

Ejecutar desde la raiz del repo:

    python -m pre_entrega_5.main

Corre tres intercambios que demuestran, en este orden:

1. Razonamiento multi-paso (dos tool calls encadenados) para responder una
   pregunta sobre un cliente que el agente identifica por nombre.
2. Memoria dentro del mismo thread_id: una segunda pregunta, sin repetir el
   nombre del cliente, que el agente entiende por el historial persistido.
3. Aislamiento entre threads: la misma pregunta en un thread_id nuevo, que
   no tiene ese contexto y por lo tanto no puede responderla sin aclaracion.
4. Manejo de un resultado "no encontrado": una pregunta sobre un cliente que
   no existe en el dataset, para mostrar que el ciclo agent -> tool -> agent
   no se cae ante un error de negocio, sino que el LLM lo interpreta solo.
"""
import asyncio
import sys

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from pre_entrega_5 import config
from pre_entrega_5.agent import construir_agente
from pre_entrega_5.persistence import crear_checkpointer
from pre_entrega_5.trace import construir_traza, guardar_traza


def _config_ejecucion(thread_id: str) -> dict:
    """Arma la config que LangGraph necesita para cada invocacion:

    - `thread_id`: identifica QUE conversacion persistida usar/actualizar.
    - `recursion_limit`: tope de vueltas agent<->tools para esta consulta.
    """
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": config.RECURSION_LIMIT,
    }


def _nombres_tools_llamadas(mensajes: list[BaseMessage]) -> list[str]:
    """Extrae, en orden, los nombres de las tools que el LLM pidio ejecutar."""
    nombres = []
    for mensaje in mensajes:
        if isinstance(mensaje, AIMessage):
            nombres.extend(llamada["name"] for llamada in mensaje.tool_calls)
    return nombres


async def preguntar(agente, thread_id: str, pregunta: str) -> list[BaseMessage]:
    """Manda una pregunta al agente en un thread_id dado.

    Imprime la pregunta, que herramientas se usaron y la respuesta final.
    Devuelve solo los mensajes NUEVOS generados en esta vuelta (sin el
    historial de turnos anteriores del mismo thread), para poder armar una
    traza clara de un unico intercambio.
    """
    print(f"\nUsuario: {pregunta}")

    cfg = _config_ejecucion(thread_id)

    # Se mide cuantos mensajes ya habia en el thread ANTES de esta pregunta,
    # para poder aislar despues solo los mensajes que agrego esta vuelta.
    estado_previo = await agente.aget_state(cfg)
    cantidad_previa = len(estado_previo.values.get("messages", [])) if estado_previo.values else 0

    resultado = await agente.ainvoke({"messages": [HumanMessage(content=pregunta)]}, config=cfg)

    mensajes_turno = resultado["messages"][cantidad_previa:]

    tools_usadas = _nombres_tools_llamadas(mensajes_turno)
    if tools_usadas:
        print(f"[Herramientas utilizadas: {' -> '.join(tools_usadas)}]")
    else:
        print("[No hizo falta usar ninguna herramienta; respondio con la memoria del thread]")

    respuesta_final = resultado["messages"][-1].content
    print(f"Respuesta: {respuesta_final}")

    return mensajes_turno


async def main() -> None:
    print("=== PRE-ENTREGA 5: AGENTE LANGGRAPH ===")

    try:
        config.validar_configuracion()
    except ValueError as error:
        print(f"\nError de configuracion: {error}")
        return

    # El checkpointer (memoria persistente en SQLite) se abre una sola vez y
    # se reutiliza para las tres consultas: asi el thread "demo-user-1" ve
    # su propio historial acumularse entre preguntas.
    async with crear_checkpointer() as checkpointer:
        agente = construir_agente(checkpointer)

        print("\n--- THREAD: demo-user-1 ---")
        mensajes_turno_1 = await preguntar(
            agente,
            "demo-user-1",
            "¿Cuántos pedidos tuvo Ana Gómez y cuánto gastó en total?",
        )

        # Se guarda este primer intercambio como ejemplo real de traza ReAct:
        # deja ver el ciclo agent -> tool -> agent -> tool -> agent completo
        # (buscar_cliente_por_nombre y despues buscar_pedidos_cliente).
        ruta_traza = config.CARPETA_TRACES / "example_trace.json"
        guardar_traza(construir_traza(mensajes_turno_1), ruta_traza)
        print(f"[Traza guardada en {ruta_traza}]")

        print("\n--- MISMO THREAD: demo-user-1 ---")
        await preguntar(agente, "demo-user-1", "¿Y cuál fue su último pedido?")

        print("\n--- THREAD NUEVO: demo-user-2 ---")
        await preguntar(agente, "demo-user-2", "¿Y cuál fue su último pedido?")

        # Martina López no existe en data/customers.json a proposito: esta
        # prueba no agrega ningun manejo especial para su caso. La tool
        # buscar_cliente_por_nombre va a devolver "encontrado": False, y es
        # el LLM quien decide, al observar ese resultado, si pide una
        # aclaracion o informa que no encontro al cliente.
        print("\n--- THREAD NUEVO: demo-error ---")
        await preguntar(
            agente,
            "demo-error",
            "¿Cuántos pedidos tuvo Martina López y cuánto gastó en total?",
        )


if __name__ == "__main__":
    # La consola de Windows por default no usa UTF-8, y esta demo imprime
    # nombres con tildes ("Ana Gómez"). Sin esto, el print() se ve con
    # caracteres corridos aunque los datos esten bien.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    asyncio.run(main())
