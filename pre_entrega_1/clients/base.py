from abc import ABC, abstractmethod  # ABC nos permite crear una clase "contrato"; abstractmethod obliga a las clases hijas a implementar ciertos métodos.
from collections.abc import AsyncGenerator  # Representa una función asíncrona que va entregando resultados de a poco, útil para streaming.

from pre_entrega_1.schemas import ChatMessage, LLMConfig, ModelResponse  # Importamos las estructuras que ya creamos en schemas.py.


class BaseLLMClient(ABC):  # Clase base que define qué debe poder hacer cualquier cliente de IA.

    def __init__(self, config: LLMConfig):  # Recibe la configuración del modelo cuando creamos el cliente.
        self.config = config  # Guardamos esa configuración para poder usarla después.

    @abstractmethod  # Obliga a OpenAIClient y AnthropicClient a crear su propia versión de generate().
    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:  # Genera una respuesta completa de forma asíncrona.
        pass  # No ponemos lógica acá porque cada proveedor funciona diferente.

    @abstractmethod  # Obliga también a cada proveedor a implementar el streaming.
    async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]:  # Va devolviendo pequeños fragmentos de texto mientras el modelo responde.
        yield  # Solo está para indicar que este método será un generador asíncrono.