import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import NewsSnapshot, NewsHeadline
from shared.settings import settings


@activity.defn
async def fetch_news_snapshot(ticker: str) -> NewsSnapshot:
    """Get the latest news for a ticker: recent headlines plus aggregate sentiment
    score (-1.0 = very negative, +1.0 = very positive). Use this tool only when the
    caller's input is missing or stale; one call returns headlines + sentiment together."""
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            h = (await c.get(f"{settings.mockoon_base_url}/news/headlines",
                             params={"ticker": ticker})).json()
            s = (await c.get(f"{settings.mockoon_base_url}/news/sentiment",
                             params={"ticker": ticker})).json()
        except httpx.HTTPError as e:
            raise ApplicationError(f"news fetch failed: {e}", type="ServerError")
    return NewsSnapshot(
        ticker=ticker,
        headlines=[NewsHeadline(**hh) for hh in h.get("headlines", [])],
        sentiment=float(s["score"]),
        rationale=str(s.get("rationale", "")),
    )
