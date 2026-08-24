from collections.abc import AsyncGenerator  # Tipo de dato para una función async que devuelve texto de a poco.

from openai import AsyncOpenAI  # Cliente ASÍNCRONO oficial de OpenAI.

from pre_entrega_1.clients.base import BaseLLMClient  # Nuestro contrato común que todos los proveedores deben respetar.
from pre_entrega_1.schemas import ChatMessage, LLMConfig, ModelResponse  # Nuestros modelos de datos creados con Pydantic.


class OpenAIClient(BaseLLMClient):  # Este cliente cumple las reglas que definimos en BaseLLMClient.

    def __init__(self, config: LLMConfig, api_key: str):  # Al crear el cliente recibe la configuración y la API Key.
        super().__init__(config)  # Guarda la configuración usando el __init__ de BaseLLMClient.
        self.client = AsyncOpenAI(api_key=api_key)  # Creamos el cliente asíncrono que realmente hablará con OpenAI.


    def _format_messages(self, messages: list[ChatMessage]) -> list[dict]:
        # OpenAI necesita recibir los mensajes como diccionarios.
        # Acá convertimos nuestros ChatMessage de Pydantic al formato que espera OpenAI.

        return [
            {"role": message.role, "content": message.content}
            for message in messages
        ]


    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        # Este método manda los mensajes a OpenAI y espera UNA respuesta completa.

        response = await self.client.chat.completions.create(  # await = esperamos a OpenAI sin bloquear todo el programa.
            model=self.config.model,  # Modelo que configuramos, por ejemplo "gpt-4o-mini".
            messages=self._format_messages(messages),  # Convertimos nuestros mensajes al formato de OpenAI.
            temperature=self.config.temperature,  # Qué tan predecible o variable queremos la respuesta.
            max_tokens=self.config.max_tokens,  # Máximo de tokens que dejamos generar.
        )

        content = response.choices[0].message.content or ""  # Sacamos solamente el texto de la respuesta de OpenAI.

        return ModelResponse(  # Convertimos la respuesta propia de OpenAI a NUESTRA respuesta estándar.
            content=content,
            provider="openai",
            model=self.config.model,
        )


    async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        # Este método también consulta OpenAI, pero devuelve la respuesta de a pequeños fragmentos.

        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=self._format_messages(messages),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,  # Le decimos a OpenAI: no esperes a tener todo listo, mandame los fragmentos mientras se generan.
        )

        async for chunk in stream:  # Vamos leyendo cada fragmento a medida que llega desde OpenAI.
            content = chunk.choices[0].delta.content  # Extraemos el pedacito de texto que acaba de llegar.

            if content:  # Algunos eventos pueden venir sin texto, por eso primero verificamos.
                yield content  # Entregamos ese fragmento sin esperar a que termine toda la respuesta.