"""Configuracion centralizada de la Pre-entrega 4.

Carga las variables de entorno desde el .env (con python-dotenv). El resto de
los modulos importan las constantes definidas aca en lugar de leer
os.environ por su cuenta, para que todo el sistema use siempre los mismos
valores (mismo modelo de embeddings, mismo indice, mismo namespace).

OJO: este modulo NO valida al importarse. La validacion es una funcion
explicita (validar_configuracion) que cada script llama al principio de su
flujo principal, adentro del try/except que ya tiene cada uno. Si esa
validacion se hiciera con un "raise" al importar el modulo, el error
apareceria como un traceback crudo la primera vez que CUALQUIER modulo de
este paquete se importe (incluso documents.py, que ni siquiera necesita las
API Keys), en lugar del mensaje prolijo que arma cada script.
"""
from pathlib import Path
import os

from dotenv import load_dotenv

# load_dotenv() sin argumentos busca un archivo .env subiendo desde el
# directorio de trabajo actual. Como todos los comandos de esta entrega se
# corren desde la raiz del repo (python -m pre_entrega_4.<modulo>), esto
# encuentra el mismo .env que ya usan pre_entrega_1 y pre_entrega_3.
load_dotenv()

# --- Credenciales y nombres (obligatorias para hablar con OpenAI/Pinecone) ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
INDEX_NAME = os.getenv("INDEX_NAME", "")
NAMESPACE = os.getenv("NAMESPACE", "")

_VARIABLES_OBLIGATORIAS = {
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "INDEX_NAME": INDEX_NAME,
    "NAMESPACE": NAMESPACE,
}


def validar_configuracion() -> None:
    """Revisa que esten todas las variables obligatorias; si falta alguna, lanza
    un ValueError con un mensaje claro de como solucionarlo. Hay que llamarla
    explicitamente al principio de cada script (setup_pinecone, ingest,
    RAGSystem), antes de hacer ninguna llamada a OpenAI o Pinecone."""
    faltantes = [nombre for nombre, valor in _VARIABLES_OBLIGATORIAS.items() if not valor]

    if faltantes:
        raise ValueError(
            "Faltan variables de entorno obligatorias: " + ", ".join(faltantes) + ".\n"
            "Copia pre_entrega_4/.env.example a .env (en la raiz del repo) y "
            "completa los valores reales (ver pre_entrega_4/README.md)."
        )


# --- Configuracion con valor por default razonable ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# text-embedding-3-small de OpenAI produce vectores de 1536 numeros. Si el
# dia de mañana se cambia el modelo de embeddings, esta constante tiene que
# actualizarse junto con el modelo, o Pinecone va a rechazar los vectores por
# no coincidir con la dimension del indice.
EMBEDDING_DIMENSION = 1536

# Similitud coseno: la metrica recomendada para embeddings de texto (importa
# la direccion del vector, no su magnitud). Ver pinecone.md para el detalle.
METRIC = "cosine"

# Region de Pinecone Serverless donde se aloja el indice.
CLOUD_PROVIDER = "aws"
REGION = "us-east-1"

# --- Chunking ---
# La consigna pide chunks de ~500-800 tokens; usamos 600 con 80 de overlap
# (un ~13%) para que una idea cortada a la mitad quede completa en al menos
# un fragmento vecino.
CHUNK_SIZE_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 80

# --- Recuperacion hibrida ---
# Candidatos que trae cada retriever ANTES de fusionar (no es el resultado
# final: EnsembleRetriever fusiona estas dos listas y despues nos quedamos
# con el top TOP_K_FINAL).
VECTOR_TOP_K = 10
BM25_TOP_K = 10
TOP_K_FINAL = 5

# Pesos iniciales, iguales para las dos señales (semantica y lexica).
ENSEMBLE_WEIGHTS = [0.5, 0.5]

# --- Rutas ---
CARPETA_ACTUAL = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA_ACTUAL / "data"
