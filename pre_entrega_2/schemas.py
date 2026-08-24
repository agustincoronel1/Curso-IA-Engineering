# Enum nos permite definir un conjunto cerrado de valores posibles.
# Lo usamos para que el nivel de criticidad SOLO pueda ser:
# "baja", "media" o "alta".
from enum import Enum

# BaseModel es la clase base de Pydantic.
# Todos nuestros esquemas de datos van a heredar de ella.
#
# Field nos permite agregar reglas y descripciones a cada campo.
from pydantic import BaseModel, Field


# Creamos un Enum para representar los únicos niveles
# de criticidad que nuestro pipeline puede devolver.
#
# Heredamos también de str para que los valores puedan serializarse
# fácilmente como strings cuando convertimos el resultado a JSON.
class NivelCriticidad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"


# Este modelo representa el "contrato de salida" de nuestro pipeline.
#
# Es decir:
# cualquier respuesta que genere el LLM deberá respetar
# esta estructura para ser considerada válida.
class TechnicalExtraction(BaseModel):

    # Lista de tecnologías encontradas dentro del texto.
    #
    # Ejemplo:
    # ["FastAPI", "Redis", "PostgreSQL"]
    #
    # min_length=1 significa que la lista debe contener
    # al menos una tecnología.
    tecnologias: list[str] = Field(
        description=(
            "Lista de tecnologías identificadas explícitamente en el texto. "
            "Si no se identifica ninguna tecnología concreta, devolver una lista vacía."
        ),
    )

    # Nivel de criticidad detectado.
    #
    # Como usamos NivelCriticidad, Pydantic solamente aceptará:
    #
    # "baja"
    # "media"
    # "alta"
    #
    # Si el LLM intenta devolver algo como "urgente",
    # la validación debería fallar.
    nivel_de_criticidad: NivelCriticidad = Field(
        description="Nivel de criticidad técnica detectado.",
    )

    # Resumen técnico del texto analizado.
    #
    # También exigimos que no sea un string vacío.
    resumen_tecnico: str = Field(
        min_length=1,
        description="Resumen breve y preciso del contenido técnico analizado.",
    )