"""Evalua el retriever hibrido contra un golden set de 5 preguntas.

Metricas usadas (definidas asi para poder medirlas de forma automatica, sin
evaluacion manual de relevancia chunk por chunk):

- Recall@5: 1.0 si AL MENOS UNO de los 5 chunks recuperados pertenece al
  documento esperado; 0.0 si ninguno pertenece.
- Precision@5: cantidad de chunks del top-5 cuyo document_id coincide con el
  documento esperado, dividido 5.

En este golden set chico consideramos "relevante" a cualquier chunk que
provenga del documento fuente esperado (no evaluamos relevancia a nivel de
cada chunk individual). Esto permite calcular las metricas de forma
reproducible sin depender de un juicio manual.

Ejecutar con:
    python -m pre_entrega_4.evaluate
"""
import json

from pre_entrega_4 import config
from pre_entrega_4.rag_system import RAGSystem


def cargar_golden_set() -> list[dict]:
    """Lee el archivo golden_set.json con las preguntas de evaluacion."""
    ruta = config.CARPETA_ACTUAL / "golden_set.json"

    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro el golden set en {ruta}")

    with ruta.open(encoding="utf-8") as archivo:
        golden_set = json.load(archivo)

    if not golden_set:
        raise ValueError("El golden set esta vacio.")

    return golden_set


def calcular_metricas(document_ids_recuperados: list[str], esperado: str) -> tuple[float, float]:
    """Calcula (precision@5, recall@5) para una pregunta a partir de los document_id recuperados.

    Precision@5 siempre divide por config.TOP_K_FINAL (k=5), no por la
    cantidad de resultados realmente devueltos: si el sistema trajera menos
    de 5 resultados, los faltantes cuentan como no relevantes en vez de
    inflar la precision achicando el denominador.
    """
    relevantes = sum(1 for doc_id in document_ids_recuperados if doc_id == esperado)

    precision = relevantes / config.TOP_K_FINAL
    recall = 1.0 if relevantes > 0 else 0.0

    return precision, recall


def evaluar() -> None:
    """Corre el golden set completo contra RAGSystem y muestra las metricas."""
    print("=" * 40)
    print("EVALUACION DEL RECUPERADOR HIBRIDO")
    print("=" * 40 + "\n")

    golden_set = cargar_golden_set()
    sistema = RAGSystem()

    precisiones: list[float] = []
    recalls: list[float] = []

    for numero, item in enumerate(golden_set, start=1):
        pregunta = item["pregunta"]
        esperado = item["documento_id_esperado"]

        resultados = sistema.search(pregunta, k=config.TOP_K_FINAL)
        chunk_ids = [doc.metadata.get("chunk_id", "?") for doc in resultados]
        document_ids = [doc.metadata.get("document_id", "?") for doc in resultados]

        precision, recall = calcular_metricas(document_ids, esperado)
        precisiones.append(precision)
        recalls.append(recall)

        print(f"Pregunta {numero}: {pregunta}")
        print(f"Documento esperado: {esperado}\n")

        print("Top-5:")
        for posicion, chunk_id in enumerate(chunk_ids, start=1):
            print(f"{posicion}. {chunk_id}")

        print(f"\nRecall@5:    {recall:.2f}")
        print(f"Precision@5: {precision:.2f}")
        print("\n" + "-" * 40 + "\n")

    recall_promedio = sum(recalls) / len(recalls)
    precision_promedio = sum(precisiones) / len(precisiones)

    print("=" * 40)
    print("RESULTADOS FINALES")
    print("=" * 40 + "\n")
    print(f"Preguntas evaluadas: {len(golden_set)}\n")
    print(f"Recall@5 promedio:    {recall_promedio:.2f}")
    print(f"Precision@5 promedio: {precision_promedio:.2f}")
    print("\n" + "=" * 40)


if __name__ == "__main__":
    try:
        evaluar()

    except ValueError as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except FileNotFoundError as error:
        print(f"\nERROR DE ARCHIVOS: {error}")

    except Exception as error:
        print(f"\nERROR EN LA EVALUACION: {type(error).__name__}: {error}")
