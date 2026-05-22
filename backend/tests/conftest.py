import pytest
from shared.models import (
    StrategySpec, MarketSnapshot, NewsSnapshot, NewsHeadline,
    Positions, TradeIntent,
)
from shared.constants import TradeAction


@pytest.fixture
def sample_strategy() -> StrategySpec:
    return StrategySpec(id="rsi-14-30-70", family="RSI",
                        params={"period": 14, "oversold": 30, "overbought": 70})


@pytest.fixture
def sample_market() -> MarketSnapshot:
    return MarketSnapshot(ticker="NVDA", price=150.0, ts=1700000000,
                          rsi=55.0, ema12=148.0, ema26=145.0, macd=0.5,
                          bb_upper=155.0, bb_lower=140.0)


@pytest.fixture
def sample_news_positive() -> NewsSnapshot:
    return NewsSnapshot(ticker="NVDA",
                        headlines=[NewsHeadline(title="NVDA beats earnings", published_at=1700000000)],
                        sentiment=0.6, rationale="positive coverage")


@pytest.fixture
def sample_news_negative() -> NewsSnapshot:
    return NewsSnapshot(ticker="NVDA",
                        headlines=[NewsHeadline(title="NVDA SEC probe announced", published_at=1700000000)],
                        sentiment=-0.7, rationale="restricted news term + low sentiment")


@pytest.fixture
def sample_intent_buy() -> TradeIntent:
    return TradeIntent(id="t-1", ticker="NVDA", action=TradeAction.BUY, qty=10, rationale="bullish")


@pytest.fixture
def sample_intent_big_buy() -> TradeIntent:
    return TradeIntent(id="t-2", ticker="NVDA", action=TradeAction.BUY, qty=100, rationale="bullish big")


@pytest.fixture
def empty_positions() -> Positions:
    return Positions()
