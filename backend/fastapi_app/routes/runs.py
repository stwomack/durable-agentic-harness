import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.models import AgentInput
from shared.strategies import default_candidate_strategies
from shared.settings import settings
from worker.workflows.hello import HelloWorkflow
from worker.workflows.parent import SelfEvolvingStockAgentWorkflow

from ..temporal_client import get_temporal_client
from ..db import insert_run, list_runs

router = APIRouter(prefix="/api/runs", tags=["runs"])


class HelloRequest(BaseModel):
    name: str


class StartRunRequest(BaseModel):
    ticker: str
    objective: str = "maximize Sharpe; max drawdown < 10%"
    history_range: str = "3y"
    num_sandboxes: int | None = None
    tick_seconds: int | None = None


class TerminateRunRequest(BaseModel):
    reason: str | None = None


@router.post("/hello")
async def start_hello(req: HelloRequest) -> dict:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        HelloWorkflow.run, req.name, id=f"hello-{req.name}",
        task_queue=settings.temporal_task_queue,
    )
    insert_run(handle.id, ticker="-", params={"name": req.name})
    return {"workflow_id": handle.id, "result": await handle.result()}


@router.post("/")
async def start_run(req: StartRunRequest) -> dict:
    n = req.num_sandboxes or settings.num_sandboxes
    inp = AgentInput(
        ticker=req.ticker.upper(),
        objective=req.objective,
        history_range=req.history_range,
        num_sandboxes=n,
        candidate_strategies=default_candidate_strategies(n),
        approval_threshold=settings.approval_threshold_usd,
        tick_seconds=req.tick_seconds or settings.tick_seconds,
    )
    workflow_id = f"agent-{req.ticker.upper()}-{uuid.uuid4().hex[:8]}"
    client = await get_temporal_client()
    await client.start_workflow(
        SelfEvolvingStockAgentWorkflow.run, inp,
        id=workflow_id, task_queue=settings.temporal_task_queue,
    )
    insert_run(workflow_id, ticker=req.ticker.upper(), params=inp.model_dump())
    return {"workflow_id": workflow_id, "ticker": req.ticker.upper()}


@router.get("/")
async def runs() -> list[dict]:
    return list_runs()


@router.post("/{workflow_id}/terminate")
async def terminate_run(workflow_id: str, body: TerminateRunRequest | None = None) -> dict:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    reason = body.reason if body and body.reason else "terminated from UI"
    try:
        await handle.terminate(reason=reason)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "workflow_id": workflow_id, "reason": reason}


@router.get("/{workflow_id}/state")
async def run_state(workflow_id: str) -> dict:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        state = await handle.query("get_state")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return state
