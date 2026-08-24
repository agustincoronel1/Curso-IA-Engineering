import logging

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from pre_entrega_2.schemas import TechnicalExtraction


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)


# include_raw=True nos permite conservar la respuesta original
# para revisar finish_reason y posibles errores de parsing.
structured_model = model.with_structured_output(
    TechnicalExtraction,
    include_raw=True,
)


def validate_response(response: dict) -> TechnicalExtraction:
    """Verifica que la respuesta esté completa y correctamente parseada."""

    raw = response["raw"]
    parsed = response["parsed"]
    parsing_error = response["parsing_error"]

    finish_reason = raw.response_metadata.get("finish_reason")

    # Si OpenAI cortó la generación por tokens u otra razón,
    # consideramos la respuesta incompleta.
    if finish_reason not in (None, "stop"):
        raise ValueError(
            f"Respuesta incompleta. finish_reason={finish_reason}"
        )

    # Si LangChain no pudo convertir la respuesta al esquema Pydantic,
    # lanzamos una excepción para activar el retry.
    if parsing_error is not None:
        raise ValueError(
            f"Error al validar la salida estructurada: {parsing_error}"
        )

    if parsed is None:
        raise ValueError("El modelo no devolvió una salida estructurada válida.")

    return parsed


# Ahora el retry envuelve tanto la generación como nuestra validación.
resilient_model = (
    structured_model
    | RunnableLambda(validate_response)
).with_retry(
    stop_after_attempt=3,
    wait_exponential_jitter=True,
)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            Sos un analista técnico especializado en arquitecturas de software
            y diagnóstico de errores.

            Analizá el texto recibido e identificá:
            - Las tecnologías mencionadas.
            - El nivel de criticidad: baja, media o alta.
            - Un resumen técnico breve y preciso.

            No inventes tecnologías.
            Si el texto no menciona ninguna tecnología concreta,
            devuelve una lista vacía en tecnologias.
            """,
        ),
        (
            "human",
            "Analizá el siguiente texto técnico:\n\n{text}",
        ),
    ]
)


chain = prompt | resilient_model


async def process_text(text: str) -> TechnicalExtraction:
    """Procesa un texto y devuelve una extracción técnica validada."""

    logger.info("Iniciando análisis técnico.")

    try:
        result = await chain.ainvoke(
            {
                "text": text,
            }
        )

        logger.info("Análisis validado correctamente.")

        return result

    except Exception:
        logger.exception(
            "El pipeline falló después de los reintentos."
        )
        raise