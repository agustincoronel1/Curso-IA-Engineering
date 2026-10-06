"""Prueba de carga: 5 POST /tasks concurrentes + polling async hasta DONE/FAILED."""

import asyncio
import os
import time

import httpx

BASE_URL = os.getenv("API_URL", "http://localhost:8000")
N = 5
QUERIES = [
    "Evaluá si conviene implementar IA para un corralón (cotizaciones y stock).",
    "Evaluá si conviene implementar un chatbot de atención al cliente en una ferretería.",
    "Evaluá si conviene automatizar el seguimiento de presupuestos en una pyme de construcción.",
    "Evaluá si conviene usar predicción de demanda de inventario en un corralón.",
    "Evaluá si conviene un asistente de WhatsApp para consultas de precios en una ferretería.",
]


async def run_one(client: httpx.AsyncClient, i: int, t0: float) -> dict:
    r = await client.post("/tasks", json={"query": QUERIES[i % len(QUERIES)]})  # sin estimated_cost: no crítica
    r.raise_for_status()
    job_id = r.json()["job_id"]
    print(f"[{i}] job_id={job_id} encolado")
    while True:
        data = (await client.get(f"/tasks/{job_id}")).json()
        if data["status"] in ("DONE", "FAILED"):
            return {"job_id": job_id, "status": data["status"], "secs": time.perf_counter() - t0, "error": data["error"]}
        await asyncio.sleep(1)


async def main() -> None:
    t0 = time.perf_counter()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        results = await asyncio.gather(*[run_one(client, i, t0) for i in range(N)])
    print("\nRESULTADOS")
    for x in results:
        print(f"{x['job_id']}  {x['status']}  {x['secs']:.1f}s  {x['error'] or ''}")
    print(f"Duración total: {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
