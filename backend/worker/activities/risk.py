from temporalio import activity

from shared.constants import RESTRICTED_NEWS_TERMS, RiskDecision, TradeAction
from shared.models import RiskCheckInput, RiskResult


def _risk_check_pure(inp: RiskCheckInput) -> RiskResult:
    if inp.intent.action == TradeAction.HOLD:
        return RiskResult(decision=RiskDecision.ALLOW, reason="HOLD")

    # Restricted news terms
    for h in inp.news.headlines:
        title = h.title.lower()
        for term in RESTRICTED_NEWS_TERMS:
            if term in title:
                return RiskResult(decision=RiskDecision.BLOCK,
                                  reason=f"restricted news term: '{term}'")

    # Sentiment
    if inp.news.sentiment < -0.5:
        return RiskResult(decision=RiskDecision.BLOCK,
                          reason=f"sentiment too negative: {inp.news.sentiment:.2f}")

    # Notional cap (use existing avg_price if we have a position, else assume 150)
    existing = inp.positions.by_ticker.get(inp.intent.ticker)
    price = existing.avg_price if existing else 150.0
    notional = inp.intent.qty * price
    if notional > inp.limits.max_notional_per_trade:
        return RiskResult(decision=RiskDecision.BLOCK,
                          reason=f"notional {notional:.0f} exceeds cap {inp.limits.max_notional_per_trade:.0f}")

    if notional > inp.approval_threshold:
        return RiskResult(decision=RiskDecision.ALLOW_REQUIRES_APPROVAL,
                          reason=f"notional {notional:.0f} > approval threshold {inp.approval_threshold:.0f}")

    return RiskResult(decision=RiskDecision.ALLOW, reason="all checks passed")


@activity.defn
async def risk_check(inp: RiskCheckInput) -> RiskResult:
    return _risk_check_pure(inp)
