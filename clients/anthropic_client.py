from collections.abc import AsyncGenerator  # Tipo usado para una función async que va devolviendo texto de a poco.

from anthropic import AsyncAnthropic  # Cliente ASÍNCRONO oficial de Anthropic.

from clients.base import BaseLLMClient  # Nuestro contrato común para todos los proveedores.
from schemas import ChatMessage, LLMConfig, ModelResponse  # Los formatos de datos que definimos con Pydantic.


class AnthropicClient(BaseLLMClient):  # Anthropic también tiene que cumplir las reglas de BaseLLMClient.

    def __init__(self, config: LLMConfig, api_key: str):  # Recibimos configuración del modelo y API Key.
        super().__init__(config)  # Guardamos la configuración en la clase base.
        self.client = AsyncAnthropic(api_key=api_key)  # Creamos el cliente async que realmente hablará con Anthropic.


    def _format_messages(self, messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        # Anthropic maneja el mensaje "system" separado de los mensajes normales.
        # Por eso acá separamos las instrucciones del sistema de los mensajes user/assistant.

        system_message = ""  # Acá vamos a guardar las instrucciones del sistema.
        formatted_messages = []  # Acá guardamos los mensajes normales de la conversación.

        for message in messages:  # Recorremos todos nuestros ChatMessage.
            if message.role == "system":  # Si es un mensaje de sistema...
                system_message = message.content  # ...lo guardamos aparte.
            else:
                formatted_messages.append(  # Si es user o assistant, lo agregamos a la conversación.
                    {
                        "role": message.role,
                        "content": message.content,
                    }
                )

        return system_message, formatted_messages  # Devolvemos ambas cosas listas para Anthropic.


    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        # Este método manda la conversación a Anthropic y espera una respuesta COMPLETA.

        system_message, formatted_messages = self._format_messages(messages)  # Adaptamos nuestros mensajes al formato de Anthropic.

        response = await self.client.messages.create(  # await = esperamos a Anthropic sin bloquear el programa.
            model=self.config.model,  # Modelo de Anthropic que elegimos.
            max_tokens=self.config.max_tokens,  # Máximo de tokens que puede generar.
            temperature=self.config.temperature,  # Qué tan variable o predecible queremos la respuesta.
            system=system_message,  # Instrucciones generales para la IA.
            messages=formatted_messages,  # Conversación user/assistant.
        )

        content = response.content[0].text  # Anthropic guarda el texto de respuesta en content[0].text.

        return ModelResponse(  # Convertimos la respuesta de Anthropic a NUESTRO formato común.
            content=content,
            provider="anthropic",
            model=self.config.model,
        )


    async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:
        # Este método devuelve la respuesta de Anthropic de a pequeños fragmentos.

        system_message, formatted_messages = self._format_messages(messages)  # Adaptamos los mensajes otra vez.

        async with self.client.messages.stream(  # Abrimos una respuesta en modo streaming.
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_message,
            messages=formatted_messages,
        ) as stream:

            async for text in stream.text_stream:  # Recorremos cada pedacito de texto a medida que Anthropic lo manda.
                yield text  # Entregamos ese fragmento inmediatamente sin esperar la respuesta completa.