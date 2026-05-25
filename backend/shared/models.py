from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .constants import Phase, RiskDecision, TradeAction


class StrategySpec(BaseModel):
    id: str
    family: Literal["RSI", "MACD", "EMA_CROSS", "BOLLINGER", "MEAN_REVERSION"]
    params: dict[str, float | int]

    def to_prompt(self) -> str:
        return f"Implement a backtest for strategy family={self.family} with params={self.params}."


class TradeLimits(BaseModel):
    max_notional_per_trade: float = 50_000
    max_daily_notional: float = 200_000
    max_position_pct: float = 0.25


class AgentInput(BaseModel):
    ticker: str
    objective: str = "maximize Sharpe; max drawdown < 10%"
    history_range: str = "3y"
    num_sandboxes: int = 8
    candidate_strategies: list[StrategySpec]
    limits: TradeLimits = Field(default_factory=TradeLimits)
    approval_threshold: float = 10_000.0
    tick_seconds: int = 10


class HistoricalDataRef(BaseModel):
    path: str
    rows: int
    ticker: str
    range: str


class Scorecard(BaseModel):
    strategy_id: str
    roi: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    generated_code: str = ""
    error: Optional[str] = None


class BacktestInput(BaseModel):
    strategy_spec: StrategySpec
    historical_data_ref: HistoricalDataRef
    sandbox_image: str


class MarketSnapshot(BaseModel):
    ticker: str
    price: float
    ts: int
    rsi: float
    ema12: float
    ema26: float
    macd: float
    bb_upper: float
    bb_lower: float


class NewsHeadline(BaseModel):
    title: str
    published_at: int


class NewsSnapshot(BaseModel):
    ticker: str
    headlines: list[NewsHeadline]
    sentiment: float
    rationale: str = ""


class Position(BaseModel):
    ticker: str
    qty: float = 0.0
    avg_price: float = 0.0


class OrderResult(BaseModel):
    order_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    status: str
    filled_qty: float
    avg_price: float


class Positions(BaseModel):
    by_ticker: dict[str, Position] = Field(default_factory=dict)

    def apply(self, order: OrderResult) -> None:
        p = self.by_ticker.get(order.ticker) or Position(ticker=order.ticker)
        if order.side == "BUY":
            new_qty = p.qty + order.filled_qty
            p.avg_price = (p.qty * p.avg_price + order.filled_qty * order.avg_price) / max(new_qty, 1e-9)
            p.qty = new_qty
        else:
            p.qty -= order.filled_qty
        self.by_ticker[order.ticker] = p


class TradeIntent(BaseModel):
    id: str
    ticker: str
    action: TradeAction
    qty: float
    rationale: str


class RiskCheckInput(BaseModel):
    intent: TradeIntent
    news: NewsSnapshot
    positions: Positions
    limits: TradeLimits
    approval_threshold: float


class RiskResult(BaseModel):
    decision: RiskDecision
    reason: str


class PlaceOrderInput(BaseModel):
    intent: TradeIntent
    idempotency_key: str


class AuditEvent(BaseModel):
    ts: datetime
    kind: str
    payload: dict


class ApprovalRequest(BaseModel):
    trade_id: str
    workflow_id: str
    intent: TradeIntent
    risk: RiskResult
    news: NewsSnapshot


class UIEvent(BaseModel):
    ts: datetime
    workflow_id: str
    kind: str
    payload: dict
