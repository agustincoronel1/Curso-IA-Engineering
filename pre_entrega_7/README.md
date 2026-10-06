# Pre-entrega 7 — Orquestador multi-agente como API asíncrona (FastAPI + Redis + LangSmith + HITL)

Expone el orquestador de la Pre-entrega 6 (Supervisor + Researcher + Analyst + Synthesizer, LangGraph) mediante una API FastAPI asíncrona. Los jobs, la cola y los checkpoints de LangGraph viven en Redis; las ejecuciones se trazan en LangSmith; las tareas críticas pausan el grafo con Human-in-the-loop real (`interrupt()` / `Command(resume=...)`).

## Arquitectura

```text
Cliente -> FastAPI (POST /tasks) -> Redis (job PENDING + cola) -> Worker async -> LangGraph -> Redis (checkpoints)
                                                                        |
                                                                        +--> LangSmith (trazas, tokens, costo, latencia)
```

- `POST /tasks` guarda el job como `PENDING` en Redis **antes** de encolarlo y responde enseguida con `job_id`. El agente nunca corre dentro del request.
- El worker (`app/worker.py`) corre como tareas asyncio lanzadas en el `lifespan` de FastAPI (`WORKER_CONCURRENCY=5` consumidores de la cola Redis). Todo es async (`redis.asyncio`, `graph.ainvoke`, `ChatOpenAI.ainvoke`).
- `thread_id` de LangGraph = `job_id`. Checkpointer: `AsyncRedisSaver` (`langgraph-checkpoint-redis`), que **requiere RediSearch**, por eso `docker-compose.yml` usa `redis/redis-stack-server`.
- Cualquier excepción del worker deja el job en `FAILED` con el error guardado.

Grafo: `START -> approval_gate -> (supervisor <-> researcher / analyst / synthesizer) -> END`. `approval_gate` es el nodo HITL; si se rechaza, va directo a `END`.

## Estructura

```text
pre_entrega_7/
├── app/
│   ├── main.py            # FastAPI: /tasks, /tasks/{id}, /tasks/{id}/approve, lifespan + workers
│   ├── graph.py           # grafo de pre_entrega_6 en async + approval_gate + checkpointer
│   ├── worker.py          # consume la cola, ejecuta/reanuda el grafo, maneja FAILED
│   ├── redis_client.py    # jobs y cola (redis.asyncio)
│   ├── observability.py   # LangSmith: config con thread_id, tags, metadata, prompt_version
│   ├── hitl.py            # criterio crítico (HITL_COST_THRESHOLD) + interrupt()
│   ├── schemas.py         # Pydantic
│   ├── state.py
│   └── agents/            # research_agent.py, analyst_agent.py
├── scripts/               # load_test.py, hitl_demo.py
├── screenshots/           # evidencia de LangSmith (ver abajo)
├── docker-compose.yml, requirements.txt, .env.example, .gitignore
```

## Instalación (Python 3.12+)

```powershell
cd pre_entrega_7
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Editar `.env` y completar `OPENAI_API_KEY` y `LANGSMITH_API_KEY` (clave de https://smith.langchain.com). Variables:

| Variable | Uso |
| --- | --- |
| `OPENAI_API_KEY`, `MODEL_NAME` | LLM |
| `REDIS_URL` | jobs, cola y checkpoints (`redis://localhost:6379/0`) |
| `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=pre-entrega-7` | observabilidad |
| `HITL_COST_THRESHOLD` | `estimated_cost >= threshold` => tarea crítica (default 10000) |

`.env` está en `.gitignore`; no subir claves.

## Ejecución

```powershell
docker compose up -d redis                       # Redis Stack en :6379 (con healthcheck y volumen)
uvicorn app.main:app --port 8000                 # API + workers
```

Al iniciar, el log indica `LangSmith ACTIVO` (sin mostrar claves).

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/tasks` | Body `{"query": str, "estimated_cost": float opcional >= 0}`. Devuelve `202 {job_id, status: PENDING}` |
| GET | `/tasks/{job_id}` | `status`, `input`, `result`, `error`, `approval_request` |
| POST | `/tasks/{job_id}/approve` | Body `{"approved": true/false, "comment": opcional}`. Solo válido en `WAITING_APPROVAL` (si no, 409). Devuelve rápido; el worker reanuda |
| GET | `/health` | Estado y threshold |

Estados: `PENDING -> RUNNING -> DONE | FAILED`, y para tareas críticas `RUNNING -> WAITING_APPROVAL -> (approve) RUNNING -> DONE`. Si se rechaza, el grafo termina de forma controlada: `status=DONE` con `result.rejected=true` y sin síntesis.

### Ejemplo normal

```powershell
curl -X POST localhost:8000/tasks -H "content-type: application/json" -d '{\"query\": \"Evaluá si conviene implementar IA en un corralón\"}'
curl localhost:8000/tasks/<job_id>
```

### Ejemplo HITL (PENDING -> RUNNING -> WAITING_APPROVAL -> approve -> RUNNING -> DONE)

```powershell
python scripts/hitl_demo.py
```

Equivale a: `POST /tasks` con `estimated_cost: 999999` (>= threshold) -> polling hasta `WAITING_APPROVAL` -> `POST /tasks/<id>/approve {"approved": true}` -> polling hasta `DONE`.

### Comprobar FAILED

Reiniciar la API con una clave inválida (`$env:OPENAI_API_KEY="invalida"; uvicorn app.main:app --port 8000`), crear una tarea normal y consultar `GET /tasks/<id>`: `status=FAILED` y `error` con la excepción.

## Prueba de carga (5 requests concurrentes) y trazas

Con Redis y la API levantados, **una sola vez**:

```powershell
python scripts/load_test.py
```

Lanza 5 `POST /tasks` concurrentes (`asyncio.gather`, tareas no críticas), imprime los 5 `job_id`, hace polling async hasta `DONE/FAILED` y muestra estado y duración. Todas las ejecuciones aparecen en LangSmith > proyecto `pre-entrega-7` (runs `orchestrator`, con nodos, LLM y tools; filtrables por tag `job:<id>` o metadata `job_id`/`thread_id`/`prompt_version`).

### Capturas a guardar en `screenshots/` (evidencia, no un informe)

Tomarlas del dashboard de **esa** corrida:

1. `traces.png` — lista de trazas de las 5 ejecuciones (y, idealmente, el detalle de una con sus nodos).
2. `cost_per_execution.png` — costo por ejecución (calculado por LangSmith desde tokens).
3. `latency_p95.png` — latencia P95 de las ejecuciones (Monitor/dashboards del proyecto); si es posible, qué nodo concentra latencia/tokens.

## Checklist de la rúbrica

- [ ] POST `/tasks` guarda `PENDING` y encola; responde sin esperar al agente (`app/main.py`)
- [ ] GET `/tasks/{id}` permite polling; worker async separado (`app/worker.py`)
- [ ] Estado, input, resultado/error, cola y checkpoints en Redis (`app/redis_client.py`, `AsyncRedisSaver`)
- [ ] `FAILED` ante excepción
- [ ] Multi-agente reutilizado de pre_entrega_6 (`app/graph.py`, `app/agents/`)
- [ ] HITL con `interrupt()` + `Command(resume=...)` en el mismo `thread_id` (`app/hitl.py`, `app/worker.py`)
- [ ] LangSmith activo (`app/observability.py`, `.env.example`)
- [ ] `scripts/load_test.py` ejecutado (5 concurrentes)
- [ ] `screenshots/traces.png`, `cost_per_execution.png`, `latency_p95.png`
- [ ] `requirements.txt`, `.env.example`, `docker-compose.yml`
