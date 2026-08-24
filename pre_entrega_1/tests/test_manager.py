# Tests de la lógica de reintentos y fallback del AsyncLLMManager.
#
# IMPORTANTE: estos tests NO llaman a OpenAI ni a Anthropic.
# Usamos "clientes falsos" que implementan el mismo contrato (BaseLLMClient)
# pero devuelven datos inventados, así que no hace falta ninguna API Key real
# ni gastar créditos.

import unittest
from unittest.mock import AsyncMock, patch  # patch nos deja reemplazar asyncio.sleep para que los tests sean instantáneos.

from pre_entrega_1.clients.base import BaseLLMClient
from pre_entrega_1.manager import AsyncLLMManager
from pre_entrega_1.schemas import ChatMessage, LLMConfig, ModelResponse


MENSAJES = [ChatMessage(role="user", content="hola")]  # Mensajes de prueba reutilizables.


class ClienteFalso(BaseLLMClient):
    # Un cliente que SIEMPRE funciona y devuelve la respuesta que le pasemos.

    def __init__(self, respuesta: ModelResponse, fragmentos: list[str] | None = None):
        super().__init__(LLMConfig(model="modelo-falso"))
        self.respuesta = respuesta
        self.fragmentos = fragmentos or []
        self.llamadas = 0  # Contamos cuántas veces nos llamaron, para poder verificarlo.

    async def generate(self, messages):
        self.llamadas += 1
        return self.respuesta

    async def stream(self, messages):
        self.llamadas += 1
        for fragmento in self.fragmentos:
            yield fragmento


class ClienteQueFalla(BaseLLMClient):
    # Un cliente que SIEMPRE falla, para simular que el proveedor está caído.

    def __init__(self):
        super().__init__(LLMConfig(model="modelo-roto"))
        self.llamadas = 0

    async def generate(self, messages):
        self.llamadas += 1
        raise RuntimeError("El proveedor está caído (simulado)")

    async def stream(self, messages):
        self.llamadas += 1
        raise RuntimeError("El proveedor está caído (simulado)")
        yield ""  # Nunca se ejecuta; está solo para que Python trate esto como generador async.


def construir_manager(cliente, cliente_fallback=None, max_retries=3) -> AsyncLLMManager:
    # Arma un manager que por dentro usa nuestros clientes falsos.
    #
    # Con patch.object reemplazamos _create_client mientras se construye el
    # manager, así NUNCA se crean los clientes reales de OpenAI/Anthropic.
    # Por eso la API Key inventada alcanza y no sale ni una petición a internet.

    with patch.object(AsyncLLMManager, "_create_client", return_value=cliente):
        manager = AsyncLLMManager(
            provider="openai",
            config=LLMConfig(model="modelo-de-prueba"),
            api_key="clave-falsa-para-tests",
            max_retries=max_retries,
        )

    manager.client = cliente
    manager.fallback_client = cliente_fallback

    return manager


class TestGenerate(unittest.IsolatedAsyncioTestCase):
    # IsolatedAsyncioTestCase nos deja escribir tests con async/await.

    async def test_proveedor_principal_exitoso(self):
        # CASO B: si el principal responde bien, devolvemos su respuesta.

        esperada = ModelResponse(content="todo ok", provider="openai", model="modelo-falso")

        principal = ClienteFalso(esperada)
        fallback = ClienteFalso(
            ModelResponse(content="no deberia usarse", provider="anthropic", model="x")
        )

        manager = construir_manager(principal, fallback)

        resultado = await manager.generate(MENSAJES)

        self.assertEqual(resultado.content, "todo ok")
        self.assertEqual(resultado.provider, "openai")
        self.assertEqual(principal.llamadas, 1)  # Se llamó una sola vez: no hubo reintentos.
        self.assertEqual(fallback.llamadas, 0)  # Y NUNCA se tocó el fallback.


    async def test_reintentos_y_despues_fallback(self):
        # CASO C: el principal falla siempre, así que se agotan los reintentos
        # y termina respondiendo el fallback.

        principal = ClienteQueFalla()
        fallback = ClienteFalso(
            ModelResponse(content="respondio el fallback", provider="anthropic", model="modelo-falso")
        )

        manager = construir_manager(principal, fallback, max_retries=3)

        # Reemplazamos asyncio.sleep por un mock: así el test no tarda los
        # segundos del backoff, pero igual podemos comprobar que se llamó.
        with patch("pre_entrega_1.manager.asyncio.sleep", new=AsyncMock()) as sleep_falso:
            resultado = await manager.generate(MENSAJES)

        self.assertEqual(resultado.content, "respondio el fallback")
        self.assertEqual(resultado.provider, "anthropic")

        self.assertEqual(principal.llamadas, 3)  # Se intentó las 3 veces configuradas.
        self.assertEqual(fallback.llamadas, 1)  # El fallback se usó una sola vez.

        # Entre 3 intentos hay 2 esperas, con backoff exponencial: 1s y después 2s.
        self.assertEqual(sleep_falso.await_count, 2)
        self.assertEqual([llamada.args[0] for llamada in sleep_falso.await_args_list], [1, 2])


    async def test_fallan_los_dos_y_se_lanza_runtime_error(self):
        # CASO D: si el principal Y el fallback fallan, queremos un error claro.

        principal = ClienteQueFalla()
        fallback = ClienteQueFalla()

        manager = construir_manager(principal, fallback, max_retries=2)

        with patch("pre_entrega_1.manager.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(RuntimeError) as contexto:
                await manager.generate(MENSAJES)

        self.assertIn("fallback", str(contexto.exception).lower())
        self.assertEqual(principal.llamadas, 2)
        self.assertEqual(fallback.llamadas, 1)


    async def test_sin_fallback_configurado_lanza_runtime_error(self):
        # Si el principal falla y ni siquiera hay fallback, también avisamos claro.

        principal = ClienteQueFalla()

        manager = construir_manager(principal, cliente_fallback=None, max_retries=2)

        with patch("pre_entrega_1.manager.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(RuntimeError) as contexto:
                await manager.generate(MENSAJES)

        self.assertIn("no hay proveedor de fallback", str(contexto.exception))
        self.assertEqual(principal.llamadas, 2)


class TestStream(unittest.IsolatedAsyncioTestCase):

    async def test_streaming_devuelve_los_fragmentos(self):
        # El streaming debe ir entregando los pedacitos de texto en orden.

        principal = ClienteFalso(
            ModelResponse(content="no se usa", provider="openai", model="modelo-falso"),
            fragmentos=["Hola", " ", "mundo"],
        )

        manager = construir_manager(principal)

        recibidos = [fragmento async for fragmento in manager.stream(MENSAJES)]

        self.assertEqual(recibidos, ["Hola", " ", "mundo"])
        self.assertEqual("".join(recibidos), "Hola mundo")


    async def test_streaming_con_error_lanza_runtime_error(self):
        # En streaming no hay reintentos ni fallback (duplicaría texto),
        # pero el error igual tiene que llegar envuelto y explicado.

        manager = construir_manager(ClienteQueFalla())

        with self.assertRaises(RuntimeError) as contexto:
            async for _ in manager.stream(MENSAJES):
                pass

        self.assertIn("falló el streaming", str(contexto.exception))


class TestCreateClient(unittest.IsolatedAsyncioTestCase):

    async def test_proveedor_no_soportado_lanza_value_error(self):
        # Un nombre mal escrito tiene que fallar al construir el manager.

        with self.assertRaises(ValueError):
            AsyncLLMManager(
                provider="proveedor-inventado",
                config=LLMConfig(model="x"),
                api_key="clave-falsa-para-tests",
            )


if __name__ == "__main__":
    unittest.main()
