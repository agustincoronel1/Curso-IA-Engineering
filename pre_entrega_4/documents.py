"""Carga de los documentos Markdown y division en chunks.

Esta funcionalidad la usan DOS lugares distintos: ingest.py (para subir los
chunks a Pinecone) y rag_system.py (para armar el indice BM25 en memoria).
Que ambos usen exactamente esta misma funcion es importante: si BM25 y
Pinecone trabajaran sobre corpus distintos (por ejemplo, con chunking
diferente), la fusion hibrida estaria comparando resultados de dos universos
de datos distintos.
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pre_entrega_4 import config

# Metadata "editorial" de cada documento del dataset. document_id es el
# identificador estable de cada fuente: se usa para armar los chunk_id
# deterministicos (fastapi_chunk_0, fastapi_chunk_1, ...) y para el golden
# set de evaluacion (evaluate.py compara contra este mismo valor).
DOCUMENTOS_INFO = [
    {
        "document_id": "fastapi",
        "archivo": "fastapi.md",
        "category": "web_framework",
        "tags": ["fastapi", "api", "python", "async"],
    },
    {
        "document_id": "pydantic",
        "archivo": "pydantic.md",
        "category": "data_validation",
        "tags": ["pydantic", "validacion", "python"],
    },
    {
        "document_id": "docker",
        "archivo": "docker.md",
        "category": "containerization",
        "tags": ["docker", "contenedores", "devops"],
    },
    {
        "document_id": "postgresql",
        "archivo": "postgresql.md",
        "category": "database",
        "tags": ["postgresql", "sql", "base_de_datos"],
    },
    {
        "document_id": "pinecone",
        "archivo": "pinecone.md",
        "category": "vector_database",
        "tags": ["pinecone", "embeddings", "vector_database"],
    },
]


def cargar_documentos_crudos() -> list[Document]:
    """Lee cada archivo Markdown completo (sin chunkear) y le agrega su metadata base."""
    if not config.CARPETA_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de datos: {config.CARPETA_DATOS}"
        )

    documentos: list[Document] = []

    for info in DOCUMENTOS_INFO:
        ruta = config.CARPETA_DATOS / info["archivo"]

        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontro el archivo de dataset esperado: {ruta}"
            )

        texto = ruta.read_text(encoding="utf-8")

        if not texto.strip():
            raise ValueError(f"El archivo {ruta} esta vacio.")

        documentos.append(
            Document(
                page_content=texto,
                metadata={
                    "document_id": info["document_id"],
                    "source": info["archivo"],
                    "category": info["category"],
                    "tags": info["tags"],
                    # Los documentos son Markdown, no PDF: no existe una
                    # pagina real. Dejamos page=1 fijo a proposito, para que
                    # el esquema de metadata ya quede preparado para el dia
                    # que se ingesten PDFs, donde cada chunk si tendria su
                    # numero de pagina real.
                    "page": 1,
                },
            )
        )

    return documentos


def dividir_en_chunks(documentos: list[Document]) -> list[Document]:
    """Divide cada documento en fragmentos de ~600 tokens (80 de overlap).

    Usa RecursiveCharacterTextSplitter.from_tiktoken_encoder para que el
    tamaño del chunk se mida en tokens reales del modelo (cl100k_base, el
    mismo tokenizador que usan los modelos de embeddings de OpenAI), no en
    caracteres.
    """
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=config.CHUNK_SIZE_TOKENS,
        chunk_overlap=config.CHUNK_OVERLAP_TOKENS,
        separators=["\n\n", "\n", " ", ""],
    )

    todos_los_chunks: list[Document] = []

    # Dividimos documento por documento (en vez de splitter.split_documents
    # sobre la lista completa) para poder numerar chunk_index desde 0 en
    # cada documento y armar IDs deterministicos tipo "fastapi_chunk_0".
    for documento in documentos:
        document_id = documento.metadata["document_id"]
        chunks_del_documento = splitter.split_documents([documento])

        for indice, chunk in enumerate(chunks_del_documento):
            chunk_id = f"{document_id}_chunk_{indice}"

            # ID deterministico (no un UUID al azar): el mismo documento
            # siempre genera los mismos chunk_id, asi que volver a correr la
            # ingesta actualiza los vectores existentes en vez de duplicarlos.
            chunk.id = chunk_id
            chunk.metadata["chunk_id"] = chunk_id
            chunk.metadata["chunk_index"] = indice

            # Guardamos el texto del chunk tambien dentro de la metadata:
            # asi cualquier resultado de busqueda trae el contenido completo
            # sin tener que ir a consultar otra base de datos aparte.
            chunk.metadata["text"] = chunk.page_content

            todos_los_chunks.append(chunk)

    return todos_los_chunks


def cargar_y_dividir_documentos() -> list[Document]:
    """Funcion de conveniencia: carga los Markdown y los divide en chunks en un solo paso."""
    documentos = cargar_documentos_crudos()
    return dividir_en_chunks(documentos)


if __name__ == "__main__":
    chunks = cargar_y_dividir_documentos()

    print(f"Documentos cargados: {len(DOCUMENTOS_INFO)}")
    print(f"Chunks generados: {len(chunks)}\n")

    for chunk in chunks:
        print(f"{chunk.metadata['chunk_id']:>20}  ({len(chunk.page_content)} caracteres)")
