import asyncio
import os

from dotenv import load_dotenv

from pre_entrega_3.ingest import CARPETA_VECTORSTORE, ingestar
from pre_entrega_3.rag import RESPUESTA_SIN_INFORMACION, get_rag_response
from pre_entrega_3.schemas import RAGResponse


# Pregunta con respuesta explicita en data/fastapi.txt.
PREGUNTA_VALIDA = "¿Qué función cumple Pydantic cuando se utiliza FastAPI?"

# Pregunta trampa: el dataset no menciona el tema, asi que el sistema debe
# responder "No lo sé" en lugar de usar el conocimiento general del modelo.
PREGUNTA_TRAMPA = "¿Cuántos campeonatos mundiales ganó la selección argentina de fútbol?"


def verificar_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "Falta la variable OPENAI_API_KEY.\n"
            "Copia .env.example a .env y completa el valor real de tu clave."
        )


def preparar_base_vectorial() -> None:
    print("=== PREPARANDO LA BASE VECTORIAL ===\n")

    if not CARPETA_VECTORSTORE.exists():
        print("No existe la base vectorial todavia. Ejecutando la ingesta...\n")

    ingestar()

    print()


def mostrar_resultado(titulo: str, pregunta: str, respuesta: RAGResponse) -> None:
    print(f"--- {titulo} ---\n")
    print("Pregunta:")
    print(pregunta)
    print()
    print("Respuesta:")
    print(respuesta.respuesta)
    print()
    print("Referencias:")

    if respuesta.referencias:
        for referencia in respuesta.referencias:
            print(f"- {referencia}")
    else:
        print("[]")

    print()


def es_respuesta_sin_informacion(respuesta: RAGResponse) -> bool:
    texto = respuesta.respuesta.strip().rstrip(".").casefold()

    return texto == RESPUESTA_SIN_INFORMACION.casefold()


async def main() -> None:
    load_dotenv()

    verificar_api_key()

    preparar_base_vectorial()

    respuesta_valida = await get_rag_response(PREGUNTA_VALIDA)
    mostrar_resultado("PRUEBA NORMAL", PREGUNTA_VALIDA, respuesta_valida)

    respuesta_trampa = await get_rag_response(PREGUNTA_TRAMPA)
    mostrar_resultado("PREGUNTA TRAMPA", PREGUNTA_TRAMPA, respuesta_trampa)

    print("--- VERIFICACION ---\n")

    if es_respuesta_sin_informacion(respuesta_trampa):
        print("OK: la pregunta trampa fue respondida con 'No lo sé'.")
    else:
        print("ATENCION: el modelo respondio la pregunta trampa con conocimiento externo.")

    if respuesta_trampa.referencias:
        print("ATENCION: la pregunta trampa devolvio referencias y no deberia.")
    else:
        print("OK: la pregunta trampa no devolvio referencias.")

    if respuesta_valida.referencias:
        print(f"OK: la pregunta valida cito {len(respuesta_valida.referencias)} fuente(s).")
    else:
        print("ATENCION: la pregunta valida no cito ninguna fuente.")


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except (ValueError, FileNotFoundError) as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except Exception as error:
        print(f"\nERROR AL EJECUTAR EL SISTEMA RAG: {type(error).__name__}: {error}")
