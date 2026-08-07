# Tests de las validaciones de Pydantic.
# No hacen ninguna llamada a OpenAI ni a Anthropic: solo crean objetos.

import unittest  # Librería estándar de Python para escribir tests.

from pydantic import ValidationError  # El error que lanza Pydantic cuando un dato no cumple las reglas.

from schemas import ChatMessage, LLMConfig, ModelResponse


class TestLLMConfig(unittest.TestCase):

    def test_config_valida_se_crea_bien(self):
        # Un caso normal: todo dentro de los límites permitidos.

        config = LLMConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=500)

        self.assertEqual(config.model, "gpt-4o-mini")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_tokens, 500)


    def test_temperature_mayor_a_2_falla(self):
        # En schemas.py pusimos le=2, así que 2.5 tiene que ser rechazado.

        with self.assertRaises(ValidationError):
            LLMConfig(model="gpt-4o-mini", temperature=2.5)


    def test_temperature_negativa_falla(self):
        # También pusimos ge=0, así que un valor negativo tiene que fallar.

        with self.assertRaises(ValidationError):
            LLMConfig(model="gpt-4o-mini", temperature=-1)


    def test_max_tokens_en_cero_falla(self):
        # En schemas.py pusimos gt=0, así que 0 no es válido.

        with self.assertRaises(ValidationError):
            LLMConfig(model="gpt-4o-mini", max_tokens=0)


    def test_max_tokens_negativo_falla(self):
        # Un valor negativo tampoco tiene sentido.

        with self.assertRaises(ValidationError):
            LLMConfig(model="gpt-4o-mini", max_tokens=-10)


class TestChatMessage(unittest.TestCase):

    def test_rol_invalido_falla(self):
        # El role está limitado con Literal a system / user / assistant.

        with self.assertRaises(ValidationError):
            ChatMessage(role="jefe", content="hola")


    def test_rol_valido_funciona(self):
        message = ChatMessage(role="user", content="¿Qué es la entropía?")

        self.assertEqual(message.role, "user")


class TestModelResponse(unittest.TestCase):

    def test_respuesta_guarda_los_tres_campos(self):
        response = ModelResponse(
            content="Una respuesta",
            provider="openai",
            model="gpt-4o-mini",
        )

        self.assertEqual(response.content, "Una respuesta")
        self.assertEqual(response.provider, "openai")
        self.assertEqual(response.model, "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
