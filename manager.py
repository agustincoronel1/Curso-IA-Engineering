#decide que hacer cuando una llamada falla
import asyncio  # Lo usamos para esperar entre reintentos sin bloquear el programa.
from collections.abc import AsyncGenerator  # Tipo usado por nuestro método de streaming.

from clients.base import BaseLLMClient  # Contrato común de todos nuestros clientes.
from clients.openai_client import OpenAIClient  # Implementación de OpenAI.
from clients.anthropic_client import AnthropicClient  # Implementación de Anthropic.
from schemas import ChatMessage, LLMConfig, ModelResponse  # Nuestros datos validados.


class AsyncLLMManager:
    # El manager decide qué cliente usar y maneja reintentos/fallback.

    def __init__(
        self,
        provider: str,
        config: LLMConfig,
        api_key: str,
        fallback_provider: str | None = None,
        fallback_config: LLMConfig | None = None,
        fallback_api_key: str | None = None,
        max_retries: int = 2,
    ):
        self.provider = provider.lower()  # Proveedor principal, por ejemplo "openai".
        self.config = config  # Configuración del proveedor principal.
        self.max_retries = max_retries  # Cantidad de veces que reintentaremos si falla.

        self.client = self._create_client(
            self.provider,
            self.config,
            api_key,
        )  # Creamos el cliente principal.

        self.fallback_client = None  # Por defecto no tenemos proveedor secundario.

        if fallback_provider and fallback_config and fallback_api_key:
            self.fallback_client = self._create_client(
                fallback_provider.lower(),
                fallback_config,
                fallback_api_key,
            )  # Si tenemos configuración de fallback, creamos también ese cliente.


    def _create_client(
        self,
        provider: str,
        config: LLMConfig,
        api_key: str,
    ) -> BaseLLMClient:
        # Esta función crea el cliente correcto según el proveedor.

        if provider == "openai":
            return OpenAIClient(config, api_key)

        if provider == "anthropic":
            return AnthropicClient(config, api_key)

        raise ValueError(f"Proveedor no soportado: {provider}")


    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        # Intenta generar una respuesta con el proveedor principal.

        for attempt in range(1, self.max_retries + 1):

            try:
                return await self.client.generate(messages)

            except Exception as error:
                print(
                    f"Intento {attempt}/{self.max_retries} "
                    f"con {self.provider} falló: {type(error).__name__}"
                )

                if attempt < self.max_retries:
                    wait_time = 2 ** (attempt - 1)  # 1s, después 2s, después 4s...
                    print(f"Reintentando en {wait_time} segundo(s)...")

                    await asyncio.sleep(wait_time)  # Esperamos sin bloquear el Event Loop.


        # Si todos los intentos fallaron, probamos el proveedor secundario.

        if self.fallback_client:
            print("Proveedor principal agotado. Intentando fallback...")

            try:
                return await self.fallback_client.generate(messages)

            except Exception as error:
                raise RuntimeError(
                    f"También falló el proveedor de fallback: {type(error).__name__}"
                ) from error


        raise RuntimeError(
            f"{self.provider} falló después de {self.max_retries} intentos "
            "y no hay proveedor de fallback disponible."
        )


    async def stream(
        self,
        messages: list[ChatMessage],
    ) -> AsyncGenerator[str, None]:
        # Streaming con el proveedor seleccionado.

        try:
            async for fragment in self.client.stream(messages):
                yield fragment

        except Exception as error:
            raise RuntimeError(
                f"Error durante el streaming con {self.provider}: "
                f"{type(error).__name__}"
            ) from error