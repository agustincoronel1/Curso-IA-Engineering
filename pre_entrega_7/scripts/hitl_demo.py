"""Demo HITL: tarea crítica -> WAITING_APPROVAL -> approve -> DONE."""

import asyncio
import os

import httpx

BASE_URL = os.getenv("API_URL", "http://localhost:8000")


async def wait_for(client: httpx.AsyncClient, job_id: str, targets: set[str]) -> dict:
    while True:
        data = (await client.get(f"/tasks/{job_id}")).json()
        print(f"  estado: {data['status']}")
        if data["status"] in targets:
            return data
        await asyncio.sleep(1)


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        r = await client.post(
            "/tasks",
            json={"query": "Evaluá si conviene implementar IA para un corralón.", "estimated_cost": 999999},
        )
        job_id = r.json()["job_id"]
        print(f"job_id={job_id}")
        data = await wait_for(client, job_id, {"WAITING_APPROVAL", "DONE", "FAILED"})
        if data["status"] != "WAITING_APPROVAL":
            raise SystemExit(f"Se esperaba WAITING_APPROVAL y fue {data['status']}: {data['error']}")
        print("Pedido de aprobación:", data["approval_request"])
        r = await client.post(f"/tasks/{job_id}/approve", json={"approved": True, "comment": "OK demo"})
        print("approve ->", r.json())
        data = await wait_for(client, job_id, {"DONE", "FAILED"})
        print("Resultado final:", (data["result"] or {}).get("final_answer") or data["error"])


if __name__ == "__main__":
    asyncio.run(main())
