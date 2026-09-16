"""Pipeline de ingesta: Markdown -> chunks -> embeddings -> Pinecone.

    documentos (.md)
        |
        v
    RecursiveCharacterTextSplitter   (documents.py)
        |
        v
    chunks con metadata
        |
        v
    OpenAIEmbeddings (text-embedding-3-small)
        |
        v
    Pinecone (por batches, en el namespace configurado)

Ejecutar con:
    python -m pre_entrega_4.ingest

Es idempotente: los chunk_id son deterministicos, asi que correr este
comando varias veces ACTUALIZA los vectores existentes en vez de duplicarlos.
No borra el indice ni el namespace antes de insertar.
"""
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from pre_entrega_4 import config
from pre_entrega_4.documents import DOCUMENTOS_INFO, cargar_y_dividir_documentos
from pre_entrega_4.setup_pinecone import configurar_indice

# Chunks por lote al insertar en Pinecone. Insertar de a 100 en vez de uno
# por uno reduce drasticamente la cantidad de llamadas de red necesarias.
TAMANO_LOTE = 100


def crear_embeddings() -> OpenAIEmbeddings:
    """Crea el cliente de embeddings de OpenAI con el modelo configurado."""
    return OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)


def abrir_vectorstore(embeddings: OpenAIEmbeddings) -> PineconeVectorStore:
    """Conecta LangChain al indice+namespace de Pinecone ya existentes."""
    return PineconeVectorStore(
        index_name=config.INDEX_NAME,
        embedding=embeddings,
        namespace=config.NAMESPACE,
        pinecone_api_key=config.PINECONE_API_KEY,
    )


def ingestar() -> None:
    """Ejecuta el pipeline completo de ingesta hacia Pinecone."""
    print("=== INGESTA A PINECONE ===\n")

    # Nos aseguramos de que el indice exista antes de insertar nada. Si ya
    # existe, configurar_indice() no hace nada y solo lo informa.
    configurar_indice()
    print()

    chunks = cargar_y_dividir_documentos()

    print(f"Documentos cargados: {len(DOCUMENTOS_INFO)}")
    for info in DOCUMENTOS_INFO:
        print(f"  - {info['archivo']} ({info['document_id']})")

    print(f"\nChunks generados: {len(chunks)}")
    print(f"Indice destino: {config.INDEX_NAME}")
    print(f"Namespace destino: {config.NAMESPACE}\n")

    embeddings = crear_embeddings()
    vectorstore = abrir_vectorstore(embeddings)

    total_insertado = 0
    total_lotes = (len(chunks) + TAMANO_LOTE - 1) // TAMANO_LOTE

    for numero_lote in range(total_lotes):
        inicio = numero_lote * TAMANO_LOTE
        fin = inicio + TAMANO_LOTE
        lote = chunks[inicio:fin]

        # Cada chunk ya tiene su chunk_id deterministico como Document.id
        # (ver documents.py). PineconeVectorStore.add_documents lo detecta
        # solo y lo usa como ID del vector: por eso correr esto de nuevo
        # sobreescribe los vectores existentes en vez de duplicarlos.
        vectorstore.add_documents(lote, namespace=config.NAMESPACE)

        total_insertado += len(lote)
        print(
            f"Lote {numero_lote + 1}/{total_lotes}: "
            f"{len(lote)} chunks insertados (acumulado: {total_insertado}/{len(chunks)})"
        )

    print(f"\nIngesta completa: {total_insertado} chunks insertados/actualizados.")
    print(f"Indice: {config.INDEX_NAME} | Namespace: {config.NAMESPACE}")


if __name__ == "__main__":
    try:
        ingestar()

    except ValueError as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except FileNotFoundError as error:
        print(f"\nERROR DE ARCHIVOS: {error}")

    except Exception as error:
        print(f"\nERROR EN LA INGESTA: {type(error).__name__}: {error}")
