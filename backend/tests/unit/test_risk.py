import pytest
from shared.constants import RiskDecision, TradeAction
from shared.models import (
    RiskCheckInput, TradeIntent, TradeLimits, NewsSnapshot, NewsHeadline, Positions,
)
from worker.activities.risk import _risk_check_pure


def make_inp(intent, news, *, approval=10_000):
    return RiskCheckInput(
        intent=intent, news=news, positions=Positions(),
        limits=TradeLimits(max_notional_per_trade=50_000),
        approval_threshold=approval,
    )


def test_block_on_restricted_news(sample_intent_buy, sample_news_negative):
    res = _risk_check_pure(make_inp(sample_intent_buy, sample_news_negative))
    assert res.decision == RiskDecision.BLOCK
    assert "restricted" in res.reason.lower() or "sentiment" in res.reason.lower()


def test_block_on_low_sentiment(sample_intent_buy):
    news = NewsSnapshot(ticker="NVDA", headlines=[NewsHeadline(title="ok", published_at=0)],
                        sentiment=-0.7)
    res = _risk_check_pure(make_inp(sample_intent_buy, news))
    assert res.decision == RiskDecision.BLOCK


def test_block_on_notional_cap(sample_news_positive):
    big_intent = TradeIntent(id="t-3", ticker="NVDA", action=TradeAction.BUY,
                             qty=1000, rationale="oversized")
    inp = RiskCheckInput(
        intent=big_intent, news=sample_news_positive, positions=Positions(),
        limits=TradeLimits(max_notional_per_trade=50_000),
        approval_threshold=10_000,
    )
    res = _risk_check_pure(inp)
    assert res.decision == RiskDecision.BLOCK
    assert "notional" in res.reason.lower()


def test_requires_approval_above_threshold(sample_intent_big_buy, sample_news_positive):
    inp = make_inp(sample_intent_big_buy, sample_news_positive, approval=100)
    res = _risk_check_pure(inp)
    assert res.decision == RiskDecision.ALLOW_REQUIRES_APPROVAL


def test_allow_when_small_and_positive(sample_intent_buy, sample_news_positive):
    res = _risk_check_pure(make_inp(sample_intent_buy, sample_news_positive, approval=1_000_000))
    assert res.decision == RiskDecision.ALLOW
