from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

from pre_entrega_3.ingest import (
    CARPETA_VECTORSTORE,
    NOMBRE_COLECCION,
    abrir_vectorstore,
    contar_chunks_indexados,
)
from pre_entrega_3.schemas import RAGResponse


load_dotenv()


TOP_K = 4

MODELO_CHAT = "gpt-4o-mini"

# Definida como constante para reutilizarla en el prompt y para que main.py
# pueda verificar la pregunta trampa comparando contra el mismo valor.
RESPUESTA_SIN_INFORMACION = "No lo sé"


def crear_retriever():
    if not Path(CARPETA_VECTORSTORE).exists():
        raise FileNotFoundError(
            f"No existe la base vectorial en {CARPETA_VECTORSTORE}.\n"
            "Ejecuta primero la ingesta: python -m pre_entrega_3.ingest"
        )

    vectorstore = abrir_vectorstore()

    if contar_chunks_indexados(vectorstore) == 0:
        raise ValueError(
            f"La coleccion '{NOMBRE_COLECCION}' esta vacia.\n"
            "Ejecuta la ingesta: python -m pre_entrega_3.ingest"
        )

    return vectorstore.as_retriever(search_kwargs={"k": TOP_K})


def formatear_documentos(documentos: list[Document]) -> str:
    bloques = []

    for documento in documentos:
        fuente = documento.metadata.get("fuente", "desconocido")
        bloques.append(f"Fuente: {fuente}\nContenido:\n{documento.page_content}")

    return "\n\n".join(bloques)


# La consigna pide PydanticOutputParser (no with_structured_output) para que el
# parseo quede como un paso explicito y visible de la cadena.
parser = PydanticOutputParser(pydantic_object=RAGResponse)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            Sos un asistente tecnico que responde preguntas sobre desarrollo
            backend usando UNICAMENTE la documentacion que se te entrega.

            REGLAS OBLIGATORIAS:

            1. Responde EXCLUSIVAMENTE con la informacion del CONTEXTO.
            2. Si la respuesta no aparece en el CONTEXTO, el campo respuesta
               debe ser exactamente: {respuesta_sin_informacion}
               y el campo referencias debe ser una lista vacia.
            3. No uses conocimiento externo, aunque conozcas la respuesta.
               Es preferible admitir que no sabes antes que inventar.
            4. No completes ni deduzcas datos que el CONTEXTO no diga.
            5. En referencias inclui SOLO los nombres de archivo que aparecen
               como "Fuente:" en los fragmentos que realmente usaste para
               responder. No agregues archivos que no hayas usado.

            FORMATO DE SALIDA:
            {format_instructions}
            """,
        ),
        (
            "human",
            """
            CONTEXTO:
            {contexto}

            PREGUNTA:
            {pregunta}
            """,
        ),
    ]
).partial(
    format_instructions=parser.get_format_instructions(),
    respuesta_sin_informacion=RESPUESTA_SIN_INFORMACION,
)


def crear_cadena_rag():
    retriever = crear_retriever()

    modelo = ChatOpenAI(model=MODELO_CHAT, temperature=0)

    preparar_entrada = {
        "contexto": retriever | RunnableLambda(formatear_documentos),
        "pregunta": RunnablePassthrough(),
    }

    return preparar_entrada | prompt | modelo | parser


# Inicializacion perezosa: si se construyera al importar, no se podria importar
# este modulo antes de correr la ingesta.
_cadena = None


def obtener_cadena():
    global _cadena

    if _cadena is None:
        _cadena = crear_cadena_rag()

    return _cadena


async def get_rag_response(query: str) -> RAGResponse:
    if not query or not query.strip():
        raise ValueError("La pregunta no puede estar vacia.")

    cadena = obtener_cadena()

    return await cadena.ainvoke(query)
