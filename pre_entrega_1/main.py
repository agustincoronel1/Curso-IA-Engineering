#configura que proveedores existen
import asyncio  # Sirve para arrancar y ejecutar nuestro código asíncrono.
import os  # Sirve para leer variables de entorno como OPENAI_API_KEY.

from dotenv import load_dotenv  # Lee las variables guardadas en el archivo .env.

from pre_entrega_1.manager import AsyncLLMManager  # Nuestro manager elige qué proveedor usar.
from pre_entrega_1.schemas import ChatMessage, LLMConfig  # Nuestros modelos de datos validados con Pydantic.


load_dotenv()  # Carga las variables del archivo .env para poder usarlas desde Python.


def build_manager() -> AsyncLLMManager:
    # Arma el manager leyendo TODO desde variables de entorno.
    # Acá decidimos quién es el proveedor principal y quién el de fallback.

    provider = os.getenv("LLM_PROVIDER", "openai").lower()  # Lee si queremos usar OpenAI o Anthropic.

    # Primero leemos los datos de los dos proveedores, sin decidir todavía cuál es cuál.
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model = os.getenv("ANTHROPIC_MODEL")


    if provider == "openai":  # Si en .env pusimos openai...
        api_key = openai_api_key  # ...OpenAI es el principal...
        model = openai_model

        fallback_provider = "anthropic"  # ...y Anthropic queda como respaldo.
        fallback_api_key = anthropic_api_key
        fallback_model = anthropic_model

    elif provider == "anthropic":  # Si elegimos Anthropic...
        api_key = anthropic_api_key  # ...Anthropic es el principal...
        model = anthropic_model

        fallback_provider = "openai"  # ...y OpenAI queda como respaldo.
        fallback_api_key = openai_api_key
        fallback_model = openai_model

    else:
        raise ValueError(f"Proveedor no soportado: {provider}")  # Evita nombres inválidos.


    if not api_key:  # Si no encontramos una API Key del principal...
        raise ValueError(f"No se encontró API Key para {provider}")  # ...paramos con un error entendible.

    if not model:  # Sin modelo tampoco podemos seguir.
        raise ValueError(f"No se encontró modelo para {provider}")


    config = LLMConfig(  # Creamos la configuración y Pydantic controla que sea válida.
        model=model,
        temperature=0.7,
        max_tokens=500,
    )


    # El fallback es OPCIONAL: solo lo configuramos si el otro proveedor
    # tiene API Key Y modelo. Si falta alguno de los dos, seguimos sin respaldo.
    fallback_config = None

    if fallback_api_key and fallback_model:
        fallback_config = LLMConfig(
            model=fallback_model,
            temperature=0.7,
            max_tokens=500,
        )
        print(f"Proveedor principal: {provider} | Fallback: {fallback_provider}")

    else:
        fallback_provider = None  # Le avisamos al manager que no hay respaldo.
        fallback_api_key = None
        print(f"Proveedor principal: {provider} | Fallback: no configurado")


    return AsyncLLMManager(  # Creamos nuestro manager ya con el fallback conectado.
        provider=provider,
        config=config,
        api_key=api_key,
        fallback_provider=fallback_provider,
        fallback_config=fallback_config,
        fallback_api_key=fallback_api_key,
        max_retries=2,  # Cuántos intentos hacemos con el principal antes de ir al fallback.
    )


async def main():  # Función principal asíncrona de nuestra aplicación.

    manager = build_manager()  # Toda la configuración quedó en la función de arriba.


    messages = [  # Creamos los mensajes que vamos a mandarle al LLM.
        ChatMessage(
            role="system",
            content="Respondé de forma clara y sencilla."
        ),
        ChatMessage(
            role="user",
            content="¿Qué es la entropía?"
        ),
    ]


    print("\n--- RESPUESTA NORMAL ---\n")

    # Si fallan el principal, sus reintentos Y el fallback, el manager lanza un error.
    # Lo atajamos acá para mostrar un mensaje claro en vez de un traceback gigante.
    try:
        response = await manager.generate(messages)  # Esperamos la respuesta completa.

        print(response.content)
        print(f"\nProveedor: {response.provider}")
        print(f"Modelo: {response.model}")

    except Exception as error:
        print(f"No se pudo generar la respuesta: {error}")


    print("\n--- RESPUESTA EN STREAMING ---\n")

    # En streaming no reintentamos: si ya empezamos a imprimir texto, volver a
    # arrancar con otro proveedor duplicaría contenido. Solo manejamos el error.
    try:
        async for fragment in manager.stream(messages):  # Recibimos fragmentos mientras el modelo genera.
            print(fragment, end="", flush=True)  # Mostramos cada fragmento inmediatamente.

        print()

    except Exception as error:
        print(f"\nError durante el streaming: {error}")


if __name__ == "__main__":
    # Este try/except atrapa los errores de configuración (falta la API Key,
    # proveedor mal escrito, etc.) para que tampoco terminen en un traceback.
    try:
        asyncio.run(main())  # Crea el Event Loop y ejecuta nuestra función main().

    except ValueError as error:
        print(f"Error de configuración: {error}")
        print("Revisá tu archivo .env (podés guiarte con .env.example).")
