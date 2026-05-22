import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import OrderResult, PlaceOrderInput
from shared.settings import settings


@activity.defn
async def place_order(inp: PlaceOrderInput) -> OrderResult:
    payload = {
        "ticker": inp.intent.ticker,
        "side": inp.intent.action.value,
        "qty": inp.intent.qty,
        "orderType": "market",
    }
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.post(
                f"{settings.mockoon_base_url}/broker/orders",
                headers={"X-Idempotency-Key": inp.idempotency_key},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise ApplicationError(f"broker 5xx: {e}", type="ServerError")
            raise ApplicationError(f"broker 4xx: {e}", type="ClientError", non_retryable=True)
        except httpx.HTTPError as e:
            raise ApplicationError(f"broker conn: {e}", type="ConnectionError")

    return OrderResult(
        order_id=str(data.get("orderId", "")),
        ticker=inp.intent.ticker,
        side=inp.intent.action.value,
        status=str(data.get("status", "unknown")),
        filled_qty=float(data.get("filledQty", inp.intent.qty)),
        avg_price=float(data.get("avgPrice", 0.0)),
    )
