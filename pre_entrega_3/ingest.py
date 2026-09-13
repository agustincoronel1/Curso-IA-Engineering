from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


load_dotenv()


CARPETA_ACTUAL = Path(__file__).resolve().parent
RAIZ_PROYECTO = CARPETA_ACTUAL.parent
CARPETA_DATOS = CARPETA_ACTUAL / "data"

# Persistimos en disco para no recalcular (y pagar) los embeddings en cada ejecucion.
CARPETA_VECTORSTORE = RAIZ_PROYECTO / "vectorstore"

NOMBRE_COLECCION = "pre_entrega_3_rag"

# rag.py importa este valor en lugar de declararlo por su cuenta: indexar y
# consultar con modelos distintos rompe la busqueda.
MODELO_EMBEDDINGS = "text-embedding-3-small"

CHUNK_SIZE_TOKENS = 500 
CHUNK_OVERLAP_TOKENS = 50

EXTENSIONES_VALIDAS = (".txt", ".md")


def crear_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=MODELO_EMBEDDINGS)


def cargar_documentos() -> list[Document]:
    if not CARPETA_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de datos: {CARPETA_DATOS}\n"
            "Crea la carpeta y pone adentro archivos .txt o .md."
        )

    documentos: list[Document] = []

    for archivo in sorted(CARPETA_DATOS.iterdir()):
        if not archivo.is_file() or archivo.suffix.lower() not in EXTENSIONES_VALIDAS:
            continue

        texto = archivo.read_text(encoding="utf-8")

        if not texto.strip():
            continue

        documentos.append(
            Document(
                page_content=texto,
                metadata={"fuente": archivo.name},
            )
        )

    if not documentos:
        raise ValueError(
            f"No se encontraron documentos .txt o .md con contenido en {CARPETA_DATOS}"
        )

    return documentos


def dividir_en_chunks(documentos: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        separators=["\n\n", "\n", " ", ""],
    )

    return splitter.split_documents(documentos)


def abrir_vectorstore() -> Chroma:
    return Chroma(
        collection_name=NOMBRE_COLECCION,
        embedding_function=crear_embeddings(),
        persist_directory=str(CARPETA_VECTORSTORE),
    )


def contar_chunks_indexados(vectorstore: Chroma) -> int:
    return len(vectorstore.get(include=[])["ids"])


def ingestar(forzar: bool = False) -> None:
    vectorstore = abrir_vectorstore()
    chunks_existentes = contar_chunks_indexados(vectorstore)

    if chunks_existentes > 0 and not forzar:
        print("La base vectorial ya esta poblada. No se vuelve a indexar.")
        print(f"Chunks ya indexados: {chunks_existentes}")
        return

    documentos = cargar_documentos()
    print(f"Documentos encontrados: {len(documentos)}")
    for documento in documentos:
        print(f"  - {documento.metadata['fuente']}")

    chunks = dividir_en_chunks(documentos)
    print(f"Chunks generados: {len(chunks)}")

    vectorstore.add_documents(chunks)

    print(f"Chunks indexados en ChromaDB: {contar_chunks_indexados(vectorstore)}")
    print(f"Carpeta de persistencia: {CARPETA_VECTORSTORE}")
    print("Base vectorial creada correctamente.")


if __name__ == "__main__":
    ingestar()
