from pathlib import Path

import httpx
import pandas as pd
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import HistoricalDataRef, MarketSnapshot
from shared.settings import settings


SHARED_DATA_DIR = Path("/data")


@activity.defn
async def fetch_historical_data(ticker: str, range_: str) -> HistoricalDataRef:
    """Fetch historical OHLCV and persist to shared volume. Returns a ref the sandbox can read."""
    SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SHARED_DATA_DIR / f"{ticker}-{range_}.parquet"

    if settings.data_mode == "live":
        try:
            import yfinance as yf
            data = yf.download(ticker, period=range_, progress=False)
            if data is None or data.empty:
                raise ApplicationError(f"yahoo returned empty for {ticker}", type="DataError",
                                       non_retryable=True)
            df = data.reset_index().rename(columns={
                "Date": "t", "Open": "o", "High": "h", "Low": "l",
                "Close": "c", "Volume": "v",
            })
            df["t"] = df["t"].astype("int64") // 10**9
        except Exception as e:
            raise ApplicationError(f"yfinance failed: {e}", type="ServerError")
    else:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(f"{settings.mockoon_base_url}/market/prices",
                            params={"ticker": ticker, "range": range_})
            r.raise_for_status()
            payload = r.json()
            df = pd.DataFrame(payload["ohlcv"])

    df.to_parquet(out_path, index=False)
    return HistoricalDataRef(path=str(out_path), rows=len(df), ticker=ticker, range=range_)


@activity.defn
async def fetch_market_snapshot(ticker: str) -> MarketSnapshot:
    """Get the latest market snapshot for a ticker: spot price plus the standard
    technical indicators (RSI, EMA12, EMA26, MACD, Bollinger bands). Use this tool
    only when the caller's input is missing or stale; one call returns everything."""
    if settings.data_mode == "live":
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="60d")
            close = float(hist["Close"].iloc[-1])
            ema12 = float(hist["Close"].ewm(span=12).mean().iloc[-1])
            ema26 = float(hist["Close"].ewm(span=26).mean().iloc[-1])
            macd = ema12 - ema26
            delta = hist["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
            loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
            rsi = 100.0 - (100.0 / (1.0 + (gain / max(loss, 1e-9)))) if loss else 50.0
            bb_std = hist["Close"].rolling(20).std().iloc[-1]
            bb_upper = ema26 + 2 * bb_std
            bb_lower = ema26 - 2 * bb_std
            import time
            return MarketSnapshot(ticker=ticker, price=close, ts=int(time.time()),
                                  rsi=float(rsi), ema12=ema12, ema26=ema26, macd=macd,
                                  bb_upper=float(bb_upper), bb_lower=float(bb_lower))
        except Exception as e:
            raise ApplicationError(f"yahoo quote failed: {e}", type="ServerError")

    async with httpx.AsyncClient(timeout=10.0) as c:
        q = (await c.get(f"{settings.mockoon_base_url}/market/quote", params={"ticker": ticker})).json()
        ind = (await c.get(f"{settings.mockoon_base_url}/market/indicators", params={"ticker": ticker})).json()
    return MarketSnapshot(
        ticker=ticker, price=float(q["price"]), ts=int(q["ts"]),
        rsi=float(ind["rsi"]), ema12=float(ind["ema12"]), ema26=float(ind["ema26"]),
        macd=float(ind["macd"]), bb_upper=float(ind["bb_upper"]), bb_lower=float(ind["bb_lower"]),
    )
