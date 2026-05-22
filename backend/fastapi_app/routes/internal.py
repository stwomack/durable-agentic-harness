from fastapi import APIRouter, Header, HTTPException

from shared.models import UIEvent
from shared.settings import settings
from ..events import bus

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/events")
async def post_event(event: UIEvent, x_internal_token: str = Header(default="")) -> dict:
    if x_internal_token != settings.fastapi_internal_token:
        raise HTTPException(status_code=401, detail="unauthorized")
    await bus.publish(event.workflow_id, event.model_dump(mode="json"))
    return {"ok": True}
