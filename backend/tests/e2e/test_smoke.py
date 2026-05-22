import pytest
import httpx


@pytest.mark.e2e
async def test_compose_health() -> None:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get("http://localhost:8000/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


@pytest.mark.e2e
async def test_hello_workflow_completes() -> None:
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post("http://localhost:8000/api/runs/hello", json={"name": "Stage"})
        assert r.status_code == 200
        data = r.json()
        assert data["result"].startswith("Hello, Stage")
        assert data["workflow_id"] == "hello-Stage"
