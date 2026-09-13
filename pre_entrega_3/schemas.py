from pydantic import BaseModel, Field


# PydanticOutputParser (ver rag.py) genera las instrucciones de formato del
# prompt a partir de este modelo, asi que las descripciones de los Field son
# literalmente lo que el LLM lee para saber que forma tiene que tener su respuesta.
class RAGResponse(BaseModel):

    respuesta: str = Field(
        description=(
            "Respuesta a la pregunta del usuario, redactada unicamente a partir "
            "del CONTEXTO recibido. Si el contexto no contiene la informacion "
            "necesaria, este campo debe ser exactamente: No lo sé"
        ),
    )

    referencias: list[str] = Field(
        default_factory=list,
        description=(
            "Lista con los nombres de los archivos del CONTEXTO que realmente "
            "respaldan la respuesta, por ejemplo: fastapi.txt. No incluir "
            "archivos que no se hayan usado. Si la respuesta es No lo sé, "
            "devolver una lista vacia."
        ),
    )
