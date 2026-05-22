from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..chaos import stop_container, start_container
from ..db import log_chaos
from ..temporal_client import get_temporal_client

router = APIRouter(prefix="/api/chaos", tags=["chaos"])


class WorkflowChaos(BaseModel):
    workflow_id: str


class InjectNewsBody(BaseModel):
    workflow_id: str
    headline: str
    sentiment: float


@router.post("/kill_worker")
async def kill_worker() -> dict:
    try:
        res = stop_container("worker")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "kill_worker", res)
    return res


@router.post("/restart_worker")
async def restart_worker() -> dict:
    try:
        res = start_container("worker")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "restart_worker", res)
    return res


@router.post("/crash_broker")
async def crash_broker() -> dict:
    try:
        res = stop_container("mockoon")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "crash_broker", res)
    return res


@router.post("/restart_broker")
async def restart_broker() -> dict:
    try:
        res = start_container("mockoon")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    log_chaos("global", "restart_broker", res)
    return res


@router.post("/fast_forward")
async def fast_forward(body: WorkflowChaos) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    await h.signal("fast_forward_tick")
    log_chaos(body.workflow_id, "fast_forward", {})
    return {"ok": True}


@router.post("/inject_news")
async def inject_news(body: InjectNewsBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    # Multi-arg signals must be passed via args=[...]; positional > 1 raises TypeError.
    await h.signal("inject_news", args=[body.headline, body.sentiment])
    log_chaos(body.workflow_id, "inject_news", body.model_dump())
    return {"ok": True}


@router.post("/force_drift")
async def force_drift(body: WorkflowChaos) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(body.workflow_id)
    await h.signal("force_drift")
    log_chaos(body.workflow_id, "force_drift", {})
    return {"ok": True}
