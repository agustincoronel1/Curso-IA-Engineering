"""Herramientas (tools) que el agente puede invocar.

Cada herramienta se define con el decorador `@tool` de LangChain, que toma el
nombre de la funcion, sus type hints y su docstring para construir la
"ficha tecnica" que despues recibe el LLM (via `bind_tools`). El LLM NUNCA ve
el codigo Python de estas funciones: decide si usarlas y con que argumentos
leyendo unicamente el docstring y la firma. Por eso los docstrings son largos
y explicitos, no un detalle de estilo.

Regla comun a las dos herramientas: nunca lanzan una excepcion por no
encontrar datos (cliente inexistente, cliente sin pedidos, etc.). En cambio,
devuelven un diccionario con "encontrado": False y un mensaje explicando que
paso. Esto es a proposito: si la tool explotara con una excepcion, el grafo
se caeria. Devolviendo un resultado estructurado, ese resultado se agrega al
historial como una `ToolMessage` mas, y es el LLM quien "observa" que falta
informacion y decide el proximo paso (probar otro nombre, pedir una
aclaracion al usuario, o explicar que no hay datos).
"""
import json

from langchain_core.tools import tool

from pre_entrega_5 import config


def _cargar_json(ruta) -> list[dict]:
    """Lee un archivo .json del dataset local y devuelve su contenido."""
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


@tool
def buscar_cliente_por_nombre(nombre: str) -> dict:
    """Busca un cliente por su nombre (completo o parcial, sin importar mayusculas).

    Usa esta herramienta cuando conoces el NOMBRE de un cliente pero todavia
    no conoces su cliente_id, que es el dato que necesitas para despues
    consultar sus pedidos con `buscar_pedidos_cliente`.

    Args:
        nombre: Nombre o parte del nombre del cliente a buscar (por ejemplo
            "Ana Gomez", "ana" o "Gomez"). No hace falta que coincida
            exactamente con mayusculas, minusculas ni acentos.

    Returns:
        Si encuentra exactamente un cliente:
            {"encontrado": True, "cliente_id": 102, "nombre": "Ana Gómez"}
        Si no encuentra ningun cliente con ese nombre:
            {"encontrado": False, "mensaje": "..."}
        Si el nombre es ambiguo y coincide con mas de un cliente:
            {"encontrado": False, "mensaje": "...",
             "coincidencias": [{"cliente_id": ..., "nombre": ...}, ...]}
            En ese caso hay que pedirle una aclaracion al usuario en vez de
            elegir un cliente al azar.
    """
    clientes = _cargar_json(config.RUTA_CUSTOMERS)
    nombre_buscado = _normalizar(nombre)

    coincidencias = [
        cliente for cliente in clientes if nombre_buscado in _normalizar(cliente["nombre"])
    ]

    if len(coincidencias) == 0:
        return {
            "encontrado": False,
            "mensaje": f"No se encontro ningun cliente cuyo nombre contenga '{nombre}'.",
        }

    if len(coincidencias) > 1:
        return {
            "encontrado": False,
            "mensaje": (
                f"'{nombre}' coincide con mas de un cliente. "
                "Pedile al usuario que aclare a cual se refiere."
            ),
            "coincidencias": coincidencias,
        }

    cliente = coincidencias[0]
    return {
        "encontrado": True,
        "cliente_id": cliente["cliente_id"],
        "nombre": cliente["nombre"],
    }


@tool
def buscar_pedidos_cliente(cliente_id: int) -> dict:
    """Devuelve los pedidos de un cliente, ya con la cantidad y el total calculados.

    Usa esta herramienta cuando ya conoces el cliente_id (por ejemplo,
    despues de llamar a `buscar_cliente_por_nombre`) y necesitas saber
    cuantos pedidos hizo, cuanto gasto en total o cual fue su ultimo pedido.

    Args:
        cliente_id: ID numerico del cliente, tal como lo devuelve
            `buscar_cliente_por_nombre`.

    Returns:
        Si el cliente tiene pedidos:
            {
                "encontrado": True,
                "cliente_id": 102,
                "cantidad_pedidos": 3,
                "total_gastado": 8800,
                "ultimo_pedido": {"pedido_id": 1003, "fecha": "2026-09-05", "total": 3100},
                "pedidos": [ ... lista completa, ordenada por fecha ... ]
            }
        Si el cliente_id no tiene ningun pedido registrado:
            {"encontrado": False, "cliente_id": 102, "mensaje": "..."}
    """
    pedidos_todos = _cargar_json(config.RUTA_ORDERS)
    pedidos_cliente = [p for p in pedidos_todos if p["cliente_id"] == cliente_id]

    if not pedidos_cliente:
        return {
            "encontrado": False,
            "cliente_id": cliente_id,
            "mensaje": f"El cliente {cliente_id} no tiene pedidos registrados.",
        }

    pedidos_cliente.sort(key=lambda p: p["fecha"])

    return {
        "encontrado": True,
        "cliente_id": cliente_id,
        "cantidad_pedidos": len(pedidos_cliente),
        "total_gastado": sum(p["total"] for p in pedidos_cliente),
        "ultimo_pedido": pedidos_cliente[-1],
        "pedidos": pedidos_cliente,
    }


def _normalizar(texto: str) -> str:
    """Minusculas y sin espacios de mas, para comparar nombres sin quisquillas."""
    return texto.strip().lower()


# Lista que consume agent.py para bind_tools() y ToolNode(). Mantenerla en un
# solo lugar evita que las dos partes del grafo terminen usando listas de
# herramientas distintas.
HERRAMIENTAS = [buscar_cliente_por_nombre, buscar_pedidos_cliente]
