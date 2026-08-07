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
| `schemas.py` | Modelos de Pydantic: `ChatMessage`, `LLMConfig` y `ModelResponse`. Define y valida las reglas de los datos. |
| `clients/base.py` | `BaseLLMClient`: la clase abstracta que fija el contrato (`generate` y `stream`) que todo proveedor debe cumplir. |
| `clients/openai_client.py` | Implementación del contrato para OpenAI. |
| `clients/anthropic_client.py` | Implementación del contrato para Anthropic (separa el mensaje `system`, como pide su API). |
| `manager.py` | `AsyncLLMManager`: elige el cliente, aplica los reintentos con backoff y deriva al fallback si hace falta. |
| `main.py` | Punto de entrada. Lee el `.env`, arma el manager y ejecuta las dos pruebas. |
| `tests/` | Tests con `unittest`. No hacen llamadas reales a ninguna API. |

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
python main.py
```

`main.py` ejecuta dos pruebas seguidas con el mismo manager:

1. **Respuesta normal** — `manager.generate(...)` espera la respuesta completa y muestra el contenido junto al proveedor y modelo que respondieron.
2. **Respuesta en streaming** — `manager.stream(...)` va imprimiendo los fragmentos a medida que llegan.

Las dos están envueltas en `try/except`, así que si fallan el principal, sus reintentos y el fallback, se muestra un mensaje claro en vez de un traceback.

## Tests

Los tests usan `unittest` (librería estándar, sin dependencias extra) y clientes falsos. **No consumen créditos ni necesitan API Keys reales.**

```powershell
python -m unittest discover -s tests -t . -v
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
main.py
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
