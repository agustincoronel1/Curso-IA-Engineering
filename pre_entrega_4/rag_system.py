"""RAGSystem: recuperacion hibrida combinando busqueda semantica (Pinecone) y
busqueda lexica (BM25) con EnsembleRetriever.

    consulta
       |
       +----------------------+
       |                      |
       v                      v
    BM25 (lexico)      Pinecone (semantico)
       |                      |
       +----------+-----------+
                  |
                  v
          EnsembleRetriever
          (Reciprocal Rank Fusion)
                  |
                  v
                top-k

No genera respuestas con un LLM: search() devuelve directamente los chunks
recuperados (langchain_core.documents.Document), para poder inspeccionar y
evaluar la calidad de la recuperacion en si misma.
"""
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from pinecone import Pinecone as PineconeClient

from pre_entrega_4 import config
from pre_entrega_4.documents import cargar_y_dividir_documentos


def _verificar_namespace_poblado() -> None:
    """Chequea que el indice y el namespace configurados existan y tengan al
    menos un vector, ANTES de armar los retrievers. Sin este chequeo, un
    namespace vacio no da ningun error: la busqueda vectorial simplemente
    devuelve cero resultados, sin explicar por que."""
    cliente = PineconeClient(api_key=config.PINECONE_API_KEY)

    if not cliente.has_index(config.INDEX_NAME):
        raise ValueError(
            f"El indice '{config.INDEX_NAME}' no existe todavia.\n"
            "Ejecuta primero: python -m pre_entrega_4.setup_pinecone"
        )

    indice = cliente.Index(config.INDEX_NAME)
    stats = indice.describe_index_stats()
    resumen_namespace = stats.namespaces.get(config.NAMESPACE)

    if resumen_namespace is None or resumen_namespace.vector_count == 0:
        raise ValueError(
            f"El namespace '{config.NAMESPACE}' del indice '{config.INDEX_NAME}' "
            "esta vacio (no tiene chunks cargados).\n"
            "Ejecuta primero: python -m pre_entrega_4.ingest"
        )


class RAGSystem:
    """Encapsula el retriever vectorial, el retriever BM25 y su fusion hibrida."""

    def __init__(self) -> None:
        config.validar_configuracion()
        _verificar_namespace_poblado()

        print("Inicializando RAGSystem...")

        embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)

        # --- Retriever SEMANTICO ---
        # Usa el mismo modelo de embeddings, el mismo indice y el mismo
        # namespace que se usaron en la ingesta (ingest.py). Si alguno de
        # estos tres valores no coincidiera con la ingesta, las busquedas
        # devolverian resultados sin sentido o directamente vacios.
        vectorstore = PineconeVectorStore(
            index_name=config.INDEX_NAME,
            embedding=embeddings,
            namespace=config.NAMESPACE,
            pinecone_api_key=config.PINECONE_API_KEY,
        )
        self.vector_retriever = vectorstore.as_retriever(
            search_kwargs={"k": config.VECTOR_TOP_K, "namespace": config.NAMESPACE}
        )

        # --- Retriever LEXICO (BM25) ---
        # BM25 corre 100% en memoria local, sin llamadas de red. Usa
        # cargar_y_dividir_documentos(), la MISMA funcion de chunking que usa
        # ingest.py para poblar Pinecone: asi las dos busquedas comparan
        # siempre sobre el mismo corpus de chunks.
        chunks = cargar_y_dividir_documentos()
        self.bm25_retriever = BM25Retriever.from_documents(chunks)
        self.bm25_retriever.k = config.BM25_TOP_K

        # --- Fusion hibrida ---
        # OJO: no se suma el score de BM25 con la similitud coseno de
        # Pinecone. Son escalas totalmente distintas (BM25 no tiene un
        # rango fijo, la similitud coseno va de -1 a 1), asi que sumarlas
        # directamente no tendria significado matematico real.
        #
        # EnsembleRetriever resuelve esto con Reciprocal Rank Fusion (RRF):
        # a cada documento se le suma weight / (rank + c) por cada lista en
        # la que aparece (rank = su posicion en esa lista, empezando en 1),
        # y el resultado final se ordena por esa suma. RRF compara
        # POSICIONES relativas dentro de cada ranking, no valores crudos,
        # por eso funciona aunque las dos escalas de score sean distintas.
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.vector_retriever, self.bm25_retriever],
            weights=config.ENSEMBLE_WEIGHTS,
            # id_key le dice al EnsembleRetriever que dos resultados son "el
            # mismo chunk" cuando comparten metadata["chunk_id"], para no
            # mostrarlo duplicado cuando lo encuentran BM25 y Pinecone a la vez.
            id_key="chunk_id",
        )

        print("RAGSystem listo.\n")

    def search(self, query: str, k: int = 5) -> list[Document]:
        """Busca `query` combinando BM25 + Pinecone y devuelve el top-k fusionado."""
        if not query or not query.strip():
            raise ValueError("La consulta no puede estar vacia.")

        # EnsembleRetriever ya devuelve la lista fusionada y ordenada por RRF;
        # si trajo mas de k resultados nos quedamos solo con los primeros k.
        resultados = self.ensemble_retriever.invoke(query)
        return resultados[:k]

    def imprimir_resultados(self, query: str, resultados: list[Document]) -> None:
        """Muestra los resultados de una busqueda de forma legible por consola."""
        print(f"=== RESULTADOS PARA: {query!r} ===\n")

        if not resultados:
            print("(sin resultados)\n")
            return

        for posicion, doc in enumerate(resultados, start=1):
            print(f"{posicion}. Fuente: {doc.metadata.get('source', '?')}")
            print(f"   Chunk: {doc.metadata.get('chunk_id', '?')}")
            print(f"   Categoria: {doc.metadata.get('category', '?')}")
            print("   Texto:")

            texto = doc.page_content.strip().replace("\n", " ")
            print(f"   {texto[:280]}{'...' if len(texto) > 280 else ''}")
            print()


if __name__ == "__main__":
    try:
        sistema = RAGSystem()

        pregunta = "¿Para qué sirve un namespace en Pinecone?"
        resultados = sistema.search(pregunta, k=config.TOP_K_FINAL)
        sistema.imprimir_resultados(pregunta, resultados)

    except ValueError as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except Exception as error:
        print(f"\nERROR AL BUSCAR: {type(error).__name__}: {error}")
