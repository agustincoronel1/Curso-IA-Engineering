# Pre-entrega 4 — RAG escalable en la nube (Pinecone + híbrido)

Sistema de **recuperación** (no de generación) que combina búsqueda semántica
en Pinecone Serverless con búsqueda léxica BM25, las fusiona con
`EnsembleRetriever` (Reciprocal Rank Fusion) y mide la calidad de esa
recuperación con Precision@5 y Recall@5 sobre un golden set de 5 preguntas.

**No hay chatbot ni LLM generando respuestas.** El alcance termina en: dado
un texto de consulta, devolver los 5 fragmentos más relevantes de la base de
conocimiento.

## Objetivo

Las pre-entregas anteriores (`pre_entrega_3/`) usaban ChromaDB, una base
vectorial **local**. Esta entrega migra la parte de almacenamiento e indexado
a **Pinecone Serverless**, una base vectorial gestionada en la nube, y agrega
una segunda señal de recuperación (BM25, léxica) para no depender solo de la
similitud semántica. Con dos señales distintas, algunas preguntas se
benefician de la búsqueda semántica (parafraseos, sinónimos) y otras de la
coincidencia léxica exacta (términos técnicos como `MVCC`, `BaseModel` o
`namespace`).

## Arquitectura

**Ingesta** (se corre una vez, o cada vez que cambia el dataset):

```text
Documentos (.md)
      |
      v
Chunking (RecursiveCharacterTextSplitter, ~600 tokens, 80 de overlap)
      |
      v
Embeddings (OpenAI text-embedding-3-small, 1536 dimensiones)
      |
      v
Pinecone Serverless (namespace "technical-docs", por batches de 100)
```

**Consulta** (recuperación híbrida):

```mermaid
flowchart TD
    Q[Consulta del usuario] --> BM25[BM25Retriever<br/>lexico, local]
    Q --> VEC[Retriever vectorial<br/>Pinecone, semantico]
    BM25 --> ENS[EnsembleRetriever<br/>Reciprocal Rank Fusion]
    VEC --> ENS
    ENS --> TOP[Top-5 fusionado]
    TOP --> EVAL[Precision@5 / Recall@5]
```

## Estructura de archivos

```text
pre_entrega_4/
├── __init__.py
├── config.py            # variables de entorno centralizadas + validacion
├── documents.py         # carga de .md + chunking (usado por ingest y BM25)
├── setup_pinecone.py    # crea el indice Serverless si no existe
├── ingest.py             # documentos -> chunks -> embeddings -> Pinecone
├── rag_system.py        # clase RAGSystem: BM25 + Pinecone + EnsembleRetriever
├── evaluate.py           # golden set -> Precision@5 / Recall@5
├── main.py                # demo: corre unas preguntas y muestra el top-5
├── data/                  # dataset propio (5 documentos Markdown)
│   ├── fastapi.md
│   ├── pydantic.md
│   ├── docker.md
│   ├── postgresql.md
│   └── pinecone.md
├── golden_set.json        # 5 preguntas de evaluacion, una por documento
├── .env.example
├── requirements.txt
└── README.md
```

## Conceptos clave

### Pinecone Serverless

Modelo de despliegue de Pinecone donde no hay que dimensionar
infraestructura manualmente: el índice escala solo y se paga por uso real
(almacenamiento + consultas), en vez de por capacidad reservada. Al crearlo
solo hace falta indicar dimensión, métrica y la región de la nube
(`setup_pinecone.py` usa AWS `us-east-1`).

### Embeddings y por qué dimensión 1536

Un embedding es la representación numérica de un texto como vector, generada
por un modelo entrenado para eso. Usamos `text-embedding-3-small` de OpenAI,
que produce vectores de **1536 números**. El índice de Pinecone se crea con
`dimension=1536` porque tiene que coincidir exactamente con la dimensión que
produce el modelo de embeddings: si no coinciden, Pinecone rechaza los
vectores. Por eso `EMBEDDING_MODEL` y `EMBEDDING_DIMENSION` viven juntos en
`config.py`, y tanto la ingesta como la búsqueda usan siempre el mismo
modelo.

### Namespace

Partición lógica dentro de un mismo índice: todos los vectores comparten
dimensión y métrica, pero se pueden separar en namespaces distintos (por
ejemplo, para aislar los documentos de distintos clientes en un sistema
multi-tenant, o distintas versiones de un dataset). Una consulta contra un
namespace solo compara contra los vectores de ese namespace. Acá se usa
`NAMESPACE=technical-docs` para todo el dataset técnico de esta entrega.

### Metadata

Cada chunk sube a Pinecone con esta metadata:

```json
{
  "document_id": "postgresql",
  "chunk_id": "postgresql_chunk_1",
  "source": "postgresql.md",
  "page": 1,
  "category": "database",
  "tags": ["postgresql", "sql", "base_de_datos"],
  "text": "...texto completo del chunk...",
  "chunk_index": 1
}
```

`page` queda fijo en `1` porque los documentos son Markdown, no PDF: no
existe una página real. El campo se conserva de todas formas porque el
mismo esquema de metadata debería poder usarse el día que se ingesten PDFs,
donde cada chunk sí tendría su número de página real.

El campo `text` guarda el contenido completo del chunk dentro de la propia
metadata, para poder leer el fragmento recuperado sin tener que consultar
otra base de datos aparte.

### Chunking

`RecursiveCharacterTextSplitter.from_tiktoken_encoder` (con el tokenizador
`cl100k_base`, el mismo que usan los modelos de OpenAI) divide cada
documento en fragmentos de **~600 tokens** con **80 tokens de overlap**
(un ~13%). El overlap evita que una idea que queda cortada justo en el borde
de un chunk pierda contexto: el final de un chunk se repite al principio del
siguiente. La misma función de chunking (`documents.py`) la usan tanto
`ingest.py` (para Pinecone) como `rag_system.py` (para BM25), así las dos
búsquedas trabajan siempre sobre el mismo corpus de chunks.

### IDs determinísticos

Los `chunk_id` son deterministas (`fastapi_chunk_0`, `fastapi_chunk_1`, ...),
no UUIDs al azar. `PineconeVectorStore.add_documents` los toma como el ID del
vector, así que volver a correr `ingest.py` sobre el mismo dataset
**actualiza** los vectores existentes en vez de duplicarlos: la ingesta es
idempotente.

### BM25 (búsqueda léxica)

BM25 es un algoritmo de ranking por coincidencia de términos (una evolución
de TF-IDF): favorece documentos que contienen las palabras exactas de la
consulta, ponderando por qué tan frecuentes son esas palabras en general.
Corre **100% local**, en memoria, con `BM25Retriever.from_documents(chunks)`
sobre los mismos chunks que se subieron a Pinecone. Es la señal que mejor
responde a consultas con términos técnicos exactos, como `MVCC PostgreSQL` o
`BaseModel Pydantic`.

### Búsqueda semántica (Pinecone)

El retriever vectorial convierte la consulta en un embedding con el mismo
modelo usado en la ingesta, y le pide a Pinecone los vectores más parecidos
por similitud coseno. Encuentra conceptos relacionados aunque la consulta no
comparta palabras exactas con el documento (por ejemplo, "aislar procesos"
puede encontrar el fragmento sobre contenedores de Docker).

### Búsqueda híbrida y EnsembleRetriever

`RAGSystem` combina ambos retrievers con `EnsembleRetriever`
(`langchain_classic.retrievers`), con pesos iniciales `[0.5, 0.5]`. Es
importante notar que **no se suman directamente** el score BM25 con la
similitud coseno de Pinecone: son escalas distintas (BM25 no tiene un rango
fijo, la similitud coseno va de -1 a 1), así que sumarlas no tendría
significado matemático real.

### Reciprocal Rank Fusion (RRF)

En cambio, `EnsembleRetriever` fusiona los dos rankings con **RRF**: a cada
documento se le suma `peso / (posición + c)` por cada lista en la que
aparece (posición empezando en 1, `c=60` por default), y el resultado final
se ordena por esa suma. RRF compara **posiciones relativas** dentro de cada
ranking, no valores crudos de score, por eso funciona aunque las dos escalas
sean incompatibles. Se configura `id_key="chunk_id"` para que, si un mismo
chunk aparece en las dos listas (BM25 y Pinecone), se cuente una sola vez en
el resultado final en lugar de aparecer duplicado.

### Precision@5 y Recall@5

Definidas así para este golden set chico, sin evaluación manual de
relevancia chunk por chunk — se considera "relevante" cualquier chunk que
provenga del documento fuente esperado:

- **Recall@5**: `1.0` si al menos uno de los 5 chunks recuperados pertenece
  al documento esperado; `0.0` si ninguno pertenece.
- **Precision@5**: cantidad de chunks del top-5 cuyo `document_id` coincide
  con el documento esperado, dividido 5.

Ejemplo: si el top-5 trae 2 chunks de `fastapi` (el esperado) y 3 de otros
documentos, `Precision@5 = 2/5 = 0.40` y `Recall@5 = 1.00` (porque al menos
uno de los 5 sí era del documento correcto).

## Reconstruir el índice desde cero

1. **Crear el entorno virtual** (si no existe uno ya para el repo):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Instalar dependencias** (además de las del `requirements.txt` de la
   raíz, esta entrega necesita las de Pinecone/BM25):

   ```powershell
   pip install -r requirements.txt
   pip install -r pre_entrega_4\requirements.txt
   ```

3. **Crear el `.env`** en la raíz del repo (si ya existe, solo agregar las
   variables nuevas al final — nunca pisar el archivo entero):

   ```powershell
   copy pre_entrega_4\.env.example .env
   ```

4. **Completar las API Keys** en `.env`: `OPENAI_API_KEY` y
   `PINECONE_API_KEY` (ver más abajo cómo conseguir la de Pinecone).
   `INDEX_NAME` y `NAMESPACE` ya vienen con un valor de ejemplo funcional.

5. **Crear el índice en Pinecone** (no hace nada si ya existe):

   ```powershell
   python -m pre_entrega_4.setup_pinecone
   ```

6. **Ejecutar la ingesta** (chunkea, genera embeddings y sube todo a
   Pinecone; es seguro correrla de nuevo, actualiza en vez de duplicar):

   ```powershell
   python -m pre_entrega_4.ingest
   ```

7. **Probar la búsqueda híbrida** con unas preguntas de ejemplo:

   ```powershell
   python -m pre_entrega_4.main
   ```

8. **Correr la evaluación** (Precision@5 / Recall@5 sobre el golden set):

   ```powershell
   python -m pre_entrega_4.evaluate
   ```

### Cómo conseguir la API Key de Pinecone (pasos manuales en la web)

Esto **no se puede automatizar** desde el código: hay que hacerlo una vez
desde la cuenta de Pinecone.

1. Crear una cuenta (o iniciar sesión) en [app.pinecone.io](https://app.pinecone.io).
2. Ir a **API Keys** en el menú del proyecto.
3. Crear una nueva key y copiar el valor.
4. Pegarlo en `.env` como `PINECONE_API_KEY=...`.

No hace falta crear el índice manualmente desde la web: `setup_pinecone.py`
lo crea por código la primera vez que se ejecuta, con `dimension=1536` y
`metric="cosine"`, usando el plan Serverless.

## Variables de entorno

| Variable | Obligatoria | Descripción |
| --- | --- | --- |
| `OPENAI_API_KEY` | Sí | Se usa para generar los embeddings (`text-embedding-3-small`). |
| `PINECONE_API_KEY` | Sí | Autentica contra la cuenta de Pinecone. |
| `INDEX_NAME` | Sí | Nombre del índice Serverless (ejemplo: `preentrega4-rag`). |
| `NAMESPACE` | Sí | Partición del índice donde se guarda este dataset (ejemplo: `technical-docs`). |
| `EMBEDDING_MODEL` | No (default `text-embedding-3-small`) | Modelo de embeddings de OpenAI. |

`config.py` NO valida al importarse: la validación es explícita, mediante la
función `config.validar_configuracion()`, que cada script llama al principio
de su flujo (`setup_pinecone.configurar_indice()` y `RAGSystem.__init__`),
adentro del mismo `try/except` que ya envuelve a cada script. Si se
validara con un `raise` directamente al importar el módulo, el error
aparecería como un traceback crudo la primera vez que se importe
**cualquier** módulo del paquete (incluso `documents.py`, que ni siquiera
necesita las API Keys), en lugar del mensaje prolijo que arma cada script.
El `.env` está en `.gitignore`: nunca se sube a Git, y `.env.example` solo
contiene placeholders, nunca claves reales.

## Manejo de errores

- **Falta `PINECONE_API_KEY` / `OPENAI_API_KEY` / `INDEX_NAME` / `NAMESPACE`**:
  `config.validar_configuracion()` lanza `ValueError` con un mensaje claro
  al principio de `setup_pinecone.configurar_indice()` y de
  `RAGSystem.__init__`, antes de intentar ninguna llamada de red.
- **Error de conexión o de la API de Pinecone** (key inválida, sin
  conexión): `setup_pinecone.py` captura `PineconeApiException` por separado
  y muestra un mensaje específico en vez de un traceback crudo.
- **Índice inexistente o namespace vacío**: antes de armar los retrievers,
  `RAGSystem.__init__` llama a `describe_index_stats()` para chequear que el
  índice exista y que el namespace configurado tenga al menos un vector. Si
  se corre `main.py` o `evaluate.py` sin haber corrido `setup_pinecone.py` o
  `ingest.py` antes, corta con un `ValueError` explícito indicando qué
  comando correr, en vez de dejar que la búsqueda vectorial devuelva
  silenciosamente cero resultados.
- **Archivos de datos faltantes o vacíos**: `documents.py` valida que
  existan los 5 archivos `.md` esperados en `data/` y que no estén vacíos,
  con `FileNotFoundError` / `ValueError` explícitos.
- **Golden set faltante o vacío**: `evaluate.py` valida la existencia y el
  contenido de `golden_set.json` antes de correr ninguna búsqueda.

## Resultados de la evaluación

> Esta sección se completa ejecutando `python -m pre_entrega_4.evaluate`
> contra un índice ya poblado (requiere `PINECONE_API_KEY` real). Todavía no
> se ejecutó contra la API real de Pinecone/OpenAI en este entorno, así que
> no hay valores para reportar — se deja el lugar marcado para no inventar
> números.

```text
Preguntas evaluadas: 5

Recall@5 promedio:    <completar tras ejecutar evaluate.py>
Precision@5 promedio: <completar tras ejecutar evaluate.py>
```

## Qué se validó sin una cuenta de Pinecone real

Antes de entregar, se probó (con datos y credenciales dummy, sin red) que:

- El chunking genera 15 chunks (3 por documento) de entre ~260 y ~600
  tokens, con IDs deterministas que no cambian entre corridas.
- `BM25Retriever` encuentra el documento correcto para consultas con
  términos técnicos exactos (por ejemplo, `MVCC PostgreSQL` devuelve primero
  los chunks de `postgresql.md`).
- `EnsembleRetriever` con `id_key="chunk_id"` fusiona dos rankings sin
  duplicar chunks que aparecen en ambos.

Lo que falta ejecutar (requiere las API Keys reales del usuario) es la
ingesta contra Pinecone y la evaluación final del golden set.

## Notas sobre las versiones de librerías usadas

El ecosistema de LangChain se reorganizó en la versión 1.x: `BM25Retriever`
vive en `langchain_community.retrievers` (con un aviso de deprecación, ya
que `langchain-community` está en proceso de discontinuarse, pero sigue
siendo la ubicación funcional vigente — no hay todavía un paquete
standalone para BM25) y `EnsembleRetriever` se movió a
`langchain_classic.retrievers`. `PineconeVectorStore` vive en el paquete
`langchain-pinecone`, separado del cliente `pinecone`. Estas ubicaciones se
verificaron contra las versiones realmente instaladas en este entorno (ver
`requirements.txt`), no copiadas de tutoriales viejos.

## No incluido a propósito (fuera de alcance de esta entrega)

- Generación de respuestas con un LLM / chatbot.
- ChromaDB o cualquier otra base vectorial local (se usa Pinecone).
- Base de datos SQL.
- FastAPI, agentes o LangGraph.

El alcance de esta entrega termina en recuperación híbrida + evaluación.
