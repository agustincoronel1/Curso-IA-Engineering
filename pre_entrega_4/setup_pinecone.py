"""Crea el indice Serverless de Pinecone si todavia no existe.

Ejecutar con:
    python -m pre_entrega_4.setup_pinecone

Este modulo NUNCA borra ni recrea un indice existente: si ya esta creado,
solo verifica que su dimension y metrica coincidan con lo esperado (1536 /
cosine) y lo informa por consola, sin modificarlo. La idea es que se pueda
correr las veces que haga falta (por ejemplo, al principio de ingest.py)
sin riesgo de perder datos.
"""
import time

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeApiException

from pre_entrega_4 import config


def obtener_cliente_pinecone() -> Pinecone:
    """Inicializa el cliente de Pinecone con la API key de la configuracion."""
    return Pinecone(api_key=config.PINECONE_API_KEY)


def crear_indice(cliente: Pinecone) -> None:
    """Crea el indice Serverless y espera a que quede disponible."""
    print("El indice no existe.")
    print("Creando indice Serverless...")

    cliente.create_index(
        name=config.INDEX_NAME,
        dimension=config.EMBEDDING_DIMENSION,
        metric=config.METRIC,
        spec=ServerlessSpec(cloud=config.CLOUD_PROVIDER, region=config.REGION),
    )

    # Crear el indice es asincrono del lado de Pinecone: esperamos activamente
    # a que quede "ready" antes de devolver el control, para que ingest.py no
    # intente insertar vectores en un indice que todavia se esta preparando.
    while not cliente.describe_index(config.INDEX_NAME).status["ready"]:
        print("  Esperando a que el indice quede disponible...")
        time.sleep(2)

    print("Indice creado correctamente.")


def verificar_indice_existente(cliente: Pinecone) -> None:
    """Si el indice ya existe, chequea que su dimension y metrica coincidan con
    la configuracion esperada. NO lo borra ni lo recrea: si no coinciden,
    corta la ejecucion con un error claro, porque seguir adelante insertaria
    (o buscaria) vectores contra un indice incompatible."""
    info = cliente.describe_index(config.INDEX_NAME)

    if info.dimension != config.EMBEDDING_DIMENSION:
        raise ValueError(
            f"El indice '{config.INDEX_NAME}' ya existe pero con dimension "
            f"{info.dimension}, distinta de la esperada ({config.EMBEDDING_DIMENSION}). "
            "No se modifica el indice automaticamente: o cambias INDEX_NAME en el "
            ".env para usar un indice nuevo, o borras el indice actual manualmente "
            "desde app.pinecone.io si estas seguro de que no tiene datos que te importen."
        )

    if info.metric != config.METRIC:
        raise ValueError(
            f"El indice '{config.INDEX_NAME}' ya existe pero con metrica "
            f"'{info.metric}', distinta de la esperada ('{config.METRIC}'). "
            "No se modifica el indice automaticamente: o cambias INDEX_NAME en el "
            ".env para usar un indice nuevo, o borras el indice actual manualmente "
            "desde app.pinecone.io si estas seguro de que no tiene datos que te importen."
        )

    print("El indice ya existe. No se vuelve a crear.")
    print(f"Dimension y metrica verificadas: {info.dimension} / {info.metric} (coinciden).")


def configurar_indice() -> None:
    """Verifica si el indice existe; si no, lo crea. Si ya existe, valida que su
    dimension y metrica coincidan con lo esperado. Es seguro llamarla varias veces."""
    config.validar_configuracion()

    print("=== CONFIGURANDO PINECONE ===\n")
    print(f"Indice: {config.INDEX_NAME}")
    print(f"Dimension: {config.EMBEDDING_DIMENSION}")
    print(f"Metrica: {config.METRIC}")
    print(f"Region: {config.CLOUD_PROVIDER}/{config.REGION}\n")

    cliente = obtener_cliente_pinecone()

    if cliente.has_index(config.INDEX_NAME):
        verificar_indice_existente(cliente)
    else:
        crear_indice(cliente)

    print("\n=== PINECONE LISTO ===")


if __name__ == "__main__":
    try:
        configurar_indice()

    except PineconeApiException as error:
        print(f"\nERROR DE PINECONE: {error}")
        print("Revisa que PINECONE_API_KEY sea correcta y que tengas conexion a internet.")

    except ValueError as error:
        print(f"\nERROR DE CONFIGURACION: {error}")

    except Exception as error:
        print(f"\nERROR INESPERADO AL CONFIGURAR PINECONE: {type(error).__name__}: {error}")
