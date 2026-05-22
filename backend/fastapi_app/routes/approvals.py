from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..temporal_client import get_temporal_client

router = APIRouter(prefix="/api/runs", tags=["approvals"])


class ApprovalBody(BaseModel):
    trade_id: str
    reason: str | None = None


@router.post("/{workflow_id}/approve")
async def approve(workflow_id: str, body: ApprovalBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(workflow_id)
    try:
        await h.signal("approve_trade", body.trade_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/{workflow_id}/reject")
async def reject(workflow_id: str, body: ApprovalBody) -> dict:
    client = await get_temporal_client()
    h = client.get_workflow_handle(workflow_id)
    try:
        await h.signal("reject_trade", args=[body.trade_id, body.reason or ""])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}
