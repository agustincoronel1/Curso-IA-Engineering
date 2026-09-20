"""Configuracion centralizada de la Pre-entrega 5.

Carga las variables de entorno con python-dotenv y expone constantes que usan
el resto de los modulos (agent.py, main.py). Sigue el mismo criterio que
pre_entrega_4/config.py: NO valida nada al importarse, la validacion es una
funcion explicita (`validar_configuracion`) que main.py llama al principio,
dentro de su propio try/except. Si validara con un `raise` al importar el
modulo, el error aparaceria como traceback crudo apenas se importe cualquier
submodulo del paquete (por ejemplo tools.py, que ni siquiera necesita la
API Key), en vez del mensaje prolijo que arma main.py.
"""
from pathlib import Path
import os

from dotenv import load_dotenv

# Sin argumentos, load_dotenv() busca el .env subiendo desde el directorio de
# trabajo actual. Como todos los comandos de esta entrega se corren desde la
# raiz del repo (python -m pre_entrega_5.main), encuentra el mismo .env que
# ya usan pre_entrega_1, pre_entrega_3 y pre_entrega_4 (misma OPENAI_API_KEY,
# sin duplicar credenciales).
load_dotenv()

# --- Credenciales (obligatoria) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Modelo (con default razonable) ---
# El repo ya usa "gpt-4o-mini" como modelo probado en pre_entrega_1 y
# pre_entrega_3 (variable OPENAI_MODEL en el .env de la raiz). Esta entrega
# pide una variable propia, MODEL_NAME, pero reutiliza el mismo valor por
# default para no depender de un modelo distinto y no probado.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")


def validar_configuracion() -> None:
    """Corta con un mensaje claro si falta la API Key.

    Hay que llamarla explicitamente al principio de main.py, antes de armar
    el modelo o el grafo, para no llegar a hacer una llamada de red con una
    key vacia.
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "Falta la variable de entorno OPENAI_API_KEY.\n"
            "Copia pre_entrega_5/.env.example a .env (en la raiz del repo) "
            "y completa tu API Key real de OpenAI. Si ya tenes un .env con "
            "OPENAI_API_KEY para otra pre-entrega, esta entrega reutiliza "
            "esa misma variable: no hace falta duplicarla."
        )


# --- Rutas ---
CARPETA_ACTUAL = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA_ACTUAL / "data"
CARPETA_TRACES = CARPETA_ACTUAL / "traces"

RUTA_CUSTOMERS = CARPETA_DATOS / "customers.json"
RUTA_ORDERS = CARPETA_DATOS / "orders.json"

# Base SQLite donde LangGraph persiste el estado de cada thread_id (memoria
# de la conversacion). Es un dato derivado/local: no se commitea a Git (ver
# .gitignore) y se regenera sola en la primera ejecucion.
RUTA_CHECKPOINTS = CARPETA_DATOS / "checkpoints.sqlite"

# Tope de vueltas del ciclo agent -> tools -> agent para una misma consulta.
# Evita loops infinitos (y gasto de tokens) si el modelo quedara pidiendo
# herramientas indefinidamente.
RECURSION_LIMIT = 10
