# Pre-entrega 1
# Unified Async LLM Client

Cliente LLM asíncrono y multiproveedor desarrollado en Python 3.12, con una interfaz común para OpenAI y Anthropic.

## Características

- Interfaz común mediante `BaseLLMClient`: todos los proveedores exponen los mismos métodos.
- Soporte para OpenAI y Anthropic.
- Async/await usando los SDK asíncronos oficiales (`AsyncOpenAI` y `AsyncAnthropic`).
- Streaming: la respuesta se va mostrando en fragmentos mientras se genera.
- Pydantic para validar la configuración y las respuestas.
- Configuración mediante variables de entorno (nada hardcodeado).
- Retries con exponential backoff asíncrono (`await asyncio.sleep`, sin bloquear el event loop).
- Fallback automático a un proveedor secundario si el principal falla.
- Manejo controlado de errores: la aplicación no termina en un traceback.

## Estructura del proyecto

| Archivo | Qué hace |
| --- | --- |
| `pre_entrega_1/schemas.py` | Modelos de Pydantic: `ChatMessage`, `LLMConfig` y `ModelResponse`. Define y valida las reglas de los datos. |
| `pre_entrega_1/clients/base.py` | `BaseLLMClient`: la clase abstracta que fija el contrato (`generate` y `stream`) que todo proveedor debe cumplir. |
| `pre_entrega_1/clients/openai_client.py` | Implementación del contrato para OpenAI. |
| `pre_entrega_1/clients/anthropic_client.py` | Implementación del contrato para Anthropic (separa el mensaje `system`, como pide su API). |
| `pre_entrega_1/manager.py` | `AsyncLLMManager`: elige el cliente, aplica los reintentos con backoff y deriva al fallback si hace falta. |
| `pre_entrega_1/main.py` | Punto de entrada. Lee el `.env`, arma el manager y ejecuta las dos pruebas. |
| `pre_entrega_1/tests/` | Tests con `unittest`. No hacen llamadas reales a ninguna API. |

## Instalación

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuración

Copiá `.env.example` a `.env` y completá los valores:

```powershell
copy .env.example .env
```

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_MODEL=...
ANTHROPIC_MODEL=...
```

`LLM_PROVIDER` define cuál es el proveedor **principal**; el otro queda automáticamente como **fallback**:

| `LLM_PROVIDER` | Principal | Fallback |
| --- | --- | --- |
| `openai` | OpenAI | Anthropic |
| `anthropic` | Anthropic | OpenAI |

El fallback solo se configura si el proveedor secundario tiene **API Key y modelo**. Si falta alguno de los dos, el programa funciona igual, pero sin respaldo.

> El archivo `.env` está ignorado por Git y **nunca debe subirse al repositorio**. En `.env.example` van únicamente placeholders, nunca claves reales.

## Ejecución

```powershell
python -m pre_entrega_1.main
```

`main.py` ejecuta dos pruebas seguidas con el mismo manager:

1. **Respuesta normal** — `manager.generate(...)` espera la respuesta completa y muestra el contenido junto al proveedor y modelo que respondieron.
2. **Respuesta en streaming** — `manager.stream(...)` va imprimiendo los fragmentos a medida que llegan.

Las dos están envueltas en `try/except`, así que si fallan el principal, sus reintentos y el fallback, se muestra un mensaje claro en vez de un traceback.

## Tests

Los tests usan `unittest` (librería estándar, sin dependencias extra) y clientes falsos. **No consumen créditos ni necesitan API Keys reales.**

```powershell
python -m unittest discover -s pre_entrega_1/tests -t . -v
```

Cubren:

- Validaciones de Pydantic (`temperature` fuera del rango 0–2, `max_tokens` menor o igual a 0, `role` inválido).
- Proveedor principal exitoso, verificando que el fallback **no** se llame.
- Reintentos agotados seguidos de un fallback exitoso, verificando la cantidad de intentos y el backoff exponencial (1s, 2s).
- Principal y fallback fallando: se lanza un `RuntimeError` controlado.
- Principal fallando sin fallback configurado: `RuntimeError` con mensaje claro.
- Streaming: fragmentos entregados en orden y errores envueltos correctamente.

## Arquitectura

```
pre_entrega_1/main.py
   ↓  (lee el .env y arma la configuración)
AsyncLLMManager        → reintentos + backoff + fallback
   ↓  (habla contra el contrato, no contra un SDK concreto)
BaseLLMClient          → generate() / stream()
   ↓
OpenAIClient  /  AnthropicClient
```

`main.py` nunca habla directamente con un SDK: solo conoce `AsyncLLMManager`, y el manager solo conoce la interfaz `BaseLLMClient`. Por eso **cambiar de proveedor no requiere modificar la lógica de negocio**: alcanza con cambiar `LLM_PROVIDER` en el `.env`. Agregar un proveedor nuevo tampoco toca `main.py`: se crea una clase que herede de `BaseLLMClient` y se la registra en el manager.

El manager además permite que un **proveedor secundario cubra al principal**: si el principal falla en todos sus intentos, la misma petición se reenvía al fallback y la aplicación sigue funcionando.

## Estado actual

- **OpenAI**: probado contra la API real, tanto en respuesta normal como en streaming.
- **Anthropic**: implementado siguiendo el mismo contrato, pero todavía no ejecutado contra la API real.
- La lógica multiproveedor (reintentos, backoff y fallback) está cubierta por los tests con clientes falsos, sin llamadas reales a ninguna API.



# Pre-entrega 2 — Pipeline de Procesamiento Validado

Pipeline asíncrono desarrollado con LangChain y LCEL para analizar textos técnicos y devolver una salida estructurada y validada con Pydantic.

## Funcionalidad

El pipeline recibe un texto técnico, como una descripción de arquitectura o un log de error, y extrae:

- Tecnologías mencionadas.
- Nivel de criticidad: baja, media o alta.
- Resumen técnico.

La salida es validada mediante un modelo Pydantic.

## Arquitectura

El flujo principal utiliza LCEL:

```text
ChatPromptTemplate
        |
        v
ChatOpenAI
        |
        v
Structured Output
        |
        v
Validación Pydantic
```


# Pre-entrega 3 — Sistema de recuperación semántica local (RAG)

Sistema RAG local: responde preguntas usando **únicamente** un dataset propio de documentos, sin depender del conocimiento general del modelo.

El flujo completo es:

```text
Documentos (.txt / .md)
        |
        v
Chunking (~500 tokens, ~50 de overlap)
        |
        v
Embeddings (text-embedding-3-small)
        |
        v
ChromaDB persistente (vectorstore/)
        |
        v
Retriever semántico (top_k = 4)
        |
        v
Prompt grounded (prohíbe conocimiento externo)
        |
        v
LLM (gpt-4o-mini, llamada asíncrona)
        |
        v
PydanticOutputParser -> RAGResponse
```

## Estructura

```text
pre_entrega_3/
├── data/                  # dataset: 4 archivos .txt sobre backend con Python
│   ├── python_backend.txt
│   ├── fastapi.txt
│   ├── postgresql.txt
│   └── docker.txt
├── ingest.py              # documentos -> chunks -> embeddings -> ChromaDB
├── rag.py                 # retriever + prompt + cadena LCEL + parser
├── schemas.py             # RAGResponse: respuesta + referencias
└── main.py                # demo: pregunta válida + pregunta trampa
```

La base vectorial se persiste en `vectorstore/`, en la raíz del proyecto. Esa carpeta está en `.gitignore`: son datos derivados, se regeneran ejecutando la ingesta.

## Instalación

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencias propias de esta entrega: `chromadb`, `langchain-chroma` y `langchain-text-splitters`.

## Variables de entorno

Esta pre-entrega solo necesita una variable, la misma que ya usa la Pre-entrega 1:

```env
OPENAI_API_KEY=
```

Se lee del `.env` con `python-dotenv`. El `.env` está ignorado por Git y en `.env.example` van únicamente placeholders, nunca claves reales.

## Ejecución

```powershell
python -m pre_entrega_3.main
```

`main.py` verifica la API key, ejecuta la ingesta **solo si hace falta** y después corre las dos pruebas.

También se puede correr la ingesta por separado:

```powershell
python -m pre_entrega_3.ingest
```

La primera ejecución indexa los 4 documentos en 12 chunks. Las siguientes detectan que la colección ya está poblada e imprimen `La base vectorial ya esta poblada. No se vuelve a indexar.`, sin volver a gastar créditos de embeddings.

## Qué hacen las pruebas

**1. Pregunta normal** — `¿Qué función cumple Pydantic cuando se utiliza FastAPI?`

La respuesta está en `data/fastapi.txt`. El retriever recupera ese fragmento y el modelo responde con lo que dice el documento, citando `fastapi.txt` en las referencias.

**2. Pregunta trampa** — `¿Cuántos campeonatos mundiales ganó la selección argentina de fútbol?`

Esa información **no** está en el dataset, pero el modelo la sabe por su entrenamiento. El retriever igual devuelve 4 fragmentos (siempre devuelve los más cercanos, aunque sean irrelevantes), y el prompt tiene que lograr que el modelo mire ese contexto, vea que no habla del tema y responda exactamente `No lo sé`, con la lista de referencias vacía.

Es la prueba clave del sistema: si respondiera el número de mundiales, no habría forma de confiar en que sus respuestas vienen de nuestros documentos.

`main.py` verifica las dos condiciones automáticamente al final e imprime `OK` o `ATENCION`.

## Conceptos aplicados

| Concepto | Qué es |
| --- | --- |
| **RAG** | Retrieval Augmented Generation. Primero se busca información en documentos propios y recién después se le pide al modelo que responda usando solo eso. |
| **Embeddings** | Traducción de un texto a un vector de números que representa su significado. Textos parecidos quedan cerca en ese espacio. |
| **Semantic search** | Búsqueda por significado, no por palabras iguales. "validar datos en FastAPI" encuentra un texto sobre "Pydantic rechaza el JSON con un 422". |
| **Chunking** | Partir cada documento en fragmentos chicos. Un embedding de un texto largo mezcla temas y se recupera mal; uno chico habla de una sola cosa. |
| **Overlap** | Cada chunk repite el final del anterior (~50 tokens), para que una idea cortada al medio quede completa en al menos un fragmento. |
| **ChromaDB** | Base de datos vectorial local. En vez de buscar por igualdad como SQL, busca por cercanía entre vectores. Persiste en disco. |
| **Retriever** | Objeto con una sola responsabilidad: dada una pregunta, devolver los documentos más relevantes. |
| **top_k** | Cuántos fragmentos se recuperan. Acá `top_k = 4`: más chunks cuestan más tokens y agregan ruido que baja la precisión. |
| **LCEL** | LangChain Expression Language: componer pasos con el operador `\|`, como una tubería. La cadena entera queda como un único objeto con `.invoke()` y `.ainvoke()`. |
| **Grounded generation** | Generación anclada a una fuente: el prompt prohíbe explícitamente usar conocimiento externo y obliga a admitir "No lo sé". |
| **PydanticOutputParser** | Genera desde el modelo Pydantic las instrucciones de formato JSON que se inyectan al prompt, y después valida la respuesta del LLM contra ese esquema. |
| **async** | Las dos operaciones caras son de red (embedding de la pregunta y generación). Con `async`/`await` el proceso no queda bloqueado durante esas esperas. |

## Salida estructurada

```python
class RAGResponse(BaseModel):
    respuesta: str
    referencias: list[str]
```

El recorrido completo de la salida estructurada es:

```text
RAGResponse
    -> PydanticOutputParser
    -> get_format_instructions()   (se inyecta en el prompt)
    -> LLM responde en JSON
    -> parser valida
    -> instancia de RAGResponse
```

Se usa `PydanticOutputParser` de forma explícita, y no `.with_structured_output()`, para que el mecanismo quede a la vista: el formato se pide con instrucciones dentro del prompt y el parseo es un paso visible de la cadena.

## Estado actual

- Probado contra la API real de OpenAI: la ingesta indexa 12 chunks y las dos preguntas se responden como se espera.
- La pregunta trampa devuelve `No lo sé` con referencias vacías.
- La persistencia funciona: en la segunda ejecución no se recalcula ningún embedding.


# Pre-entrega 4 — RAG escalable en la nube (Pinecone + búsqueda híbrida)

Sistema de **recuperación** (sin generación con LLM) que migra el almacenamiento vectorial de la Pre-entrega 3 de ChromaDB local a **Pinecone Serverless**, y agrega búsqueda léxica **BM25** combinada con la semántica mediante `EnsembleRetriever` (Reciprocal Rank Fusion). Se evalúa con `Precision@5` y `Recall@5` sobre un golden set de 5 preguntas.

```text
Documentos (.md)  ->  Chunking (~600 tokens)  ->  Embeddings (1536 dim)  ->  Pinecone

Consulta  ->  BM25 (léxico) + Pinecone (semántico)  ->  EnsembleRetriever (RRF)  ->  Top-5  ->  Precision@5 / Recall@5
```

Documentación completa, arquitectura, decisiones técnicas y pasos para reconstruir el índice: **[`pre_entrega_4/README.md`](pre_entrega_4/README.md)**.

## Ejecución

```powershell
python -m pre_entrega_4.setup_pinecone
python -m pre_entrega_4.ingest
python -m pre_entrega_4.main
python -m pre_entrega_4.evaluate
```
