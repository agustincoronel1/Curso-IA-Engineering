#configura que proveedores existen
import asyncio  # Sirve para arrancar y ejecutar nuestro código asíncrono.
import os  # Sirve para leer variables de entorno como OPENAI_API_KEY.

from dotenv import load_dotenv  # Lee las variables guardadas en el archivo .env.

from manager import AsyncLLMManager  # Nuestro manager elige qué proveedor usar.
from schemas import ChatMessage, LLMConfig  # Nuestros modelos de datos validados con Pydantic.


load_dotenv()  # Carga las variables del archivo .env para poder usarlas desde Python.


async def main():  # Función principal asíncrona de nuestra aplicación.

    provider = os.getenv("LLM_PROVIDER", "openai")  # Lee si queremos usar OpenAI o Anthropic.

    if provider == "openai":  # Si en .env pusimos openai...
        api_key = os.getenv("OPENAI_API_KEY")  # Tomamos la API Key de OpenAI.
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Tomamos el modelo de OpenAI.

    elif provider == "anthropic":  # Si elegimos Anthropic...
        api_key = os.getenv("ANTHROPIC_API_KEY")  # Tomamos su API Key.
        model = os.getenv("ANTHROPIC_MODEL")  # Tomamos su modelo.

    else:
        raise ValueError(f"Proveedor no soportado: {provider}")  # Evita nombres inválidos.


    if not api_key:  # Si no encontramos una API Key...
        raise ValueError(f"No se encontró API Key para {provider}")  # ...paramos con un error entendible.


    config = LLMConfig(  # Creamos la configuración y Pydantic controla que sea válida.
        model=model,
        temperature=0.7,
        max_tokens=500,
    )


    manager = AsyncLLMManager(  # Creamos nuestro manager.
        provider=provider,
        config=config,
        api_key=api_key,
    )


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

    response = await manager.generate(messages)  # Esperamos la respuesta completa.

    print(response.content)
    print(f"\nProveedor: {response.provider}")
    print(f"Modelo: {response.model}")


    print("\n--- RESPUESTA EN STREAMING ---\n")

    async for fragment in manager.stream(messages):  # Recibimos fragmentos mientras el modelo genera.
        print(fragment, end="", flush=True)  # Mostramos cada fragmento inmediatamente.

    print()


if __name__ == "__main__":
    asyncio.run(main())  # Crea el Event Loop y ejecuta nuestra función main().