"""Demo del sistema de recuperacion hibrido: corre unas preguntas de prueba y
muestra el top-5 de chunks recuperados para cada una.

IMPORTANTE: esto NO es un chatbot. No se llama a ningun LLM para generar una
respuesta en lenguaje natural; solo se muestra que fragmentos recupera el
sistema hibrido (BM25 + Pinecone) para cada pregunta.

Requiere que la ingesta ya se haya ejecutado (python -m pre_entrega_4.ingest).

Ejecutar con:
    python -m pre_entrega_4.main
"""
from pre_entrega_4 import config
from pre_entrega_4.rag_system import RAGSystem

PREGUNTAS_DE_PRUEBA = [
    "¿Para qué sirve un namespace cuando guardamos vectores de diferentes clientes?",
    "¿Qué significa MVCC en PostgreSQL?",
    "¿Cuál es la diferencia entre una imagen y un contenedor de Docker?",
]


def main() -> None:
    sistema = RAGSystem()

    for pregunta in PREGUNTAS_DE_PRUEBA:
        resultados = sistema.search(pregunta, k=config.TOP_K_FINAL)
        sistema.imprimir_resultados(pregunta, resultados)
        print("-" * 40 + "\n")


if __name__ == "__main__":
    try:
        main()

    except ValueError as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except Exception as error:
        print(f"\nERROR AL EJECUTAR EL SISTEMA: {type(error).__name__}: {error}")
