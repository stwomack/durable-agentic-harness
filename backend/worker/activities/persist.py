import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import StrategySpec, OrderResult
from shared.settings import settings


@activity.defn
async def persist_strategy(strategy: StrategySpec) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(f"{settings.mockoon_base_url}/db/strategy", json=strategy.model_dump())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"db/strategy 5xx: {e}", type="ServerError")
            raise ApplicationError(f"db/strategy 4xx: {e}", type="ClientError", non_retryable=True)


@activity.defn
async def write_trade_record(order: OrderResult) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(f"{settings.mockoon_base_url}/db/trades", json=order.model_dump())
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"db/trades 5xx: {e}", type="ServerError")
            raise ApplicationError(f"db/trades 4xx: {e}", type="ClientError", non_retryable=True)
