import asyncio

from pydantic import ValidationError

from pre_entrega_2.chain import process_text
from langchain_core.runnables import RunnableLambda

# Caso normal: contiene tecnologías y un problema técnico claro.
NORMAL_TEXT = """
La API desarrollada con FastAPI utiliza Redis como sistema de caché
y PostgreSQL para persistencia. Bajo alta concurrencia aparecen
timeouts y se agota el pool de conexiones de la base de datos.
"""


# Caso más ambiguo para probar cómo se comporta el pipeline
# cuando la información técnica no es tan clara.
AMBIGUOUS_TEXT = """
El sistema está funcionando más lento de lo habitual.
Algunos usuarios informan demoras, pero todavía no se identificó
con precisión cuál es el componente responsable.
"""

# Contador para saber cuántas veces se ejecutó la prueba.
retry_attempts = 0


async def unstable_operation(_: str) -> str:
    """Simula una operación que falla dos veces y funciona en la tercera."""

    global retry_attempts
    retry_attempts += 1

    print(f"Intento de retry: {retry_attempts}")

    if retry_attempts < 3:
        raise ValueError("Fallo simulado")

    return "Operación completada correctamente"


# Convertimos nuestra función en un Runnable de LangChain
# y le agregamos la misma estrategia de retry del pipeline real.
retry_test = RunnableLambda(unstable_operation).with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=True,
)

async def run_test(name: str, text: str) -> None:
    """Ejecuta un caso de prueba y muestra el resultado."""

    print(f"\n--- {name} ---")

    try:
        result = await process_text(text)

        # model_dump_json convierte el objeto Pydantic
        # en JSON para verlo fácilmente en consola.
        print(result.model_dump_json(indent=2))

    except ValidationError as exc:
        print("La respuesta no cumplió el esquema Pydantic:")
        print(exc)

    except Exception as exc:
        print(f"El pipeline terminó con un error: {exc}")


async def main():
    await run_test(
        "PRUEBA NORMAL",
        NORMAL_TEXT,
    )

    await run_test(
        "PRUEBA AMBIGUA",
        AMBIGUOUS_TEXT,
    )

    print("\n--- PRUEBA DE RETRY ---")

    try:
        result = await retry_test.ainvoke("test")
        print(result)

    except Exception as exc:
        print(f"El retry falló: {exc}")

if __name__ == "__main__":
    asyncio.run(main())