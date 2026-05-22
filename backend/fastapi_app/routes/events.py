import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..events import bus

router = APIRouter(prefix="/api/runs", tags=["events"])


@router.get("/{workflow_id}/events")
async def stream(workflow_id: str) -> EventSourceResponse:
    async def event_gen():
        async for event in bus.subscribe(workflow_id):
            # sse-starlette str()s non-string `data`, which gives Python dict repr
            # (single quotes) and breaks JSON.parse in the browser. Serialize ourselves.
            yield {"event": event["kind"], "data": json.dumps(event)}
    return EventSourceResponse(event_gen())
