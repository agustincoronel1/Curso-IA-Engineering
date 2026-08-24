# archivo donde definimos las reglas de los datos de nuestra aplicación
from typing import Literal  # Sirve para limitar una variable a opciones específicas.
from enum import Enum

from pydantic import BaseModel, Field  # BaseModel valida datos; Field agrega reglas y valores por defecto.


class ChatMessage(BaseModel):  # Representa un mensaje dentro de la conversación.
    role: Literal["system", "user", "assistant"]  # Indica quién habla: sistema, usuario o IA.
    content: str  # Es el texto del mensaje, por ejemplo: "¿Qué es la entropía?"


class LLMConfig(BaseModel):  # Guarda la configuración que vamos a usar para llamar al modelo.
    model: str  # Nombre del modelo que queremos usar, por ejemplo "gpt-4o-mini".
    temperature: float = Field(default=0.7, ge=0, le=2)  # Controla qué tan variable es la respuesta: bajo = más predecible, alto = más variado. Si no ponemos nada usa 0.7 y solo acepta valores entre 0 y 2.
    max_tokens: int = Field(default=500, gt=0)  # Limita cuánto texto puede generar la IA. Si no ponemos nada usa 500 y siempre debe ser mayor a 0.


class ModelResponse(BaseModel):  # Define cómo queremos guardar la respuesta del modelo.
    content: str  # Texto que generó la IA.
    provider: str  # Proveedor que respondió, por ejemplo "openai" o "anthropic".
    model: str  # Modelo específico que respondió, por ejemplo "gpt-4o-mini".

