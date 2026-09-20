"""Checkpointer de SQLite: la memoria persistente del agente.

Un "checkpointer" es el mecanismo que usa LangGraph para guardar, despues de
cada paso del grafo, el estado completo (en este caso, la lista de mensajes)
asociado a un `thread_id`. Sin checkpointer, cada llamada a `graph.ainvoke`
arranca de cero. Con un checkpointer de SQLite, el historial queda guardado
en un archivo .sqlite en disco: se puede cerrar el programa y, al volver a
correrlo con el mismo thread_id, el agente sigue la conversacion donde
quedo.

Version instalada: `langgraph-checkpoint-sqlite==3.1.1` (paquete separado de
`langgraph`, agregado a requirements.txt). Esa version SOLO expone
`AsyncSqliteSaver` (en `langgraph.checkpoint.sqlite.aio`) como conexion
async real: `from_conn_string` abre la conexion con `aiosqlite` y hay que
usarla como context manager async (`async with ... as checkpointer:`).
Existe tambien `SqliteSaver` (sync) en `langgraph.checkpoint.sqlite`, pero
como esta entrega corre todo el grafo con `await graph.ainvoke(...)` /
`asyncio.run(main())`, se usa la variante async para no mezclar una conexion
sincrona de sqlite3 dentro de un event loop asincrono.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from pre_entrega_5 import config


@asynccontextmanager
async def crear_checkpointer() -> AsyncIterator[AsyncSqliteSaver]:
    """Abre (o crea) la base `data/checkpoints.sqlite` como checkpointer async.

    Se usa como:

        async with crear_checkpointer() as checkpointer:
            agente = construir_agente(checkpointer)
            ...
    """
    config.CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(config.RUTA_CHECKPOINTS)) as checkpointer:
        yield checkpointer
