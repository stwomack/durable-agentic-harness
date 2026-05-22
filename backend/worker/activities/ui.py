import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import UIEvent
from shared.settings import settings


@activity.defn
async def notify_ui(event: UIEvent) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            r = await c.post(
                f"{settings.fastapi_internal_url}/internal/events",
                headers={"X-Internal-Token": settings.fastapi_internal_token},
                json=event.model_dump(mode="json"),
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"notify_ui 5xx: {e}", type="ServerError")
            raise ApplicationError(f"notify_ui 4xx: {e}", type="ClientError", non_retryable=True)
        except httpx.RequestError as e:
            raise ApplicationError(f"notify_ui connection: {e}", type="ConnectionError")
