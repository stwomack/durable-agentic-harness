"""SelfEvolvingStockAgentWorkflow — the durable harness for the trading agent.

Two phases:
  1. SYNTHESIZING — fan out N child backtests, pick the winner, persist.
  2. WATCHING / AWAITING_APPROVAL — every tick, run the OpenAI Agent SDK to get
     a TradeIntent, deterministically risk-check it, gate on human approval if
     needed, place the order.

The OpenAI Agents SDK integration is in `_run_trade_agent`. The `OpenAIAgentsPlugin`
configured on the Worker auto-dispatches each Agent LLM call as a durable Temporal
activity, so the entire agentic loop survives worker crashes.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

# Temporal sandboxes workflow modules and blocks imports that touch the
# filesystem, network, or random state at import time. The OpenAI Agents SDK
# (`agents`) and the Temporal plugin glue (`openai_agents`) trip those checks
# during import, so we explicitly mark them as trusted — they're safe to import
# even though the sandbox can't prove it.
with workflow.unsafe.imports_passed_through():
    from agents import Agent, Runner
    from temporalio.contrib import openai_agents as temporal_agents
    from shared.constants import Phase, RiskDecision, TradeAction
    from shared.models import (
        AgentInput, BacktestInput, MarketSnapshot, NewsHeadline, NewsSnapshot,
        PlaceOrderInput, Positions, RiskCheckInput, Scorecard, StrategySpec,
        TradeIntent, UIEvent,
    )
    from shared.prompts import LIVE_AGENT_PROMPT
    from shared.selection import select_winner
    from shared.settings import settings
    from worker.workflows.backtest import BacktestSandboxWorkflow
    from worker.activities.market import fetch_historical_data, fetch_market_snapshot
    from worker.activities.news import fetch_news_snapshot
    from worker.activities.risk import risk_check
    from worker.activities.broker import place_order
    from worker.activities.persist import persist_strategy, write_trade_record
    from worker.activities.ui import notify_ui


# ───── Activity execution policies (DRY) ─────
_RETRY_STANDARD = RetryPolicy(maximum_attempts=50)
_T_SHORT  = dict(start_to_close_timeout=timedelta(seconds=10),  retry_policy=_RETRY_STANDARD)
_T_MEDIUM = dict(start_to_close_timeout=timedelta(seconds=120),  retry_policy=_RETRY_STANDARD)
_T_LONG   = dict(start_to_close_timeout=timedelta(seconds=500), retry_policy=RetryPolicy(maximum_attempts=3))


@dataclass
class ChaosNews:
    """Headline + sentiment override injected via the `inject_news` signal.

    Applies to the next 2 ticks (TTL) so the stage chaos action is clearly visible
    to the audience even if the next tick fires immediately after the button click.
    """
    extra_headlines: list[NewsHeadline] = field(default_factory=list)
    sentiment_override: Optional[float] = None
    ttl: int = 0

    def apply(self, news: NewsSnapshot) -> bool:
        """Mutate `news` in place if there's pending injection. Returns True if applied."""
        applied = False
        if self.extra_headlines:
            news.headlines.extend(self.extra_headlines)
            self.extra_headlines = []
            applied = True
        if self.ttl > 0 and self.sentiment_override is not None:
            news.sentiment = self.sentiment_override
            self.ttl -= 1
            applied = True
            if self.ttl == 0:
                self.sentiment_override = None
        return applied


@workflow.defn
class SelfEvolvingStockAgentWorkflow:
    def __init__(self) -> None:
        self.phase: Phase = Phase.SYNTHESIZING
        self.winning_strategy: Optional[StrategySpec] = None
        self.scorecards: list[Scorecard] = []
        self.positions: Positions = Positions()
        self.tick_count: int = 0
        self._approvals: dict[str, bool] = {}
        self._chaos_news: ChaosNews = ChaosNews()
        self._fast_forward: bool = False
        self._stop: bool = False

    # ───── Signals ─────
    @workflow.signal
    def approve_trade(self, trade_id: str) -> None:
        self._approvals[trade_id] = True

    @workflow.signal
    def reject_trade(self, trade_id: str, reason: str = "") -> None:
        self._approvals[trade_id] = False

    @workflow.signal
    def fast_forward_tick(self) -> None:
        self._fast_forward = True

    @workflow.signal
    def inject_news(self, headline: str, sentiment: float) -> None:
        self._chaos_news.extra_headlines.append(NewsHeadline(title=headline, published_at=0))
        self._chaos_news.sentiment_override = sentiment
        self._chaos_news.ttl = 2

    @workflow.signal
    def stop(self) -> None:
        self._stop = True

    @workflow.query
    def get_state(self) -> dict:
        return {
            "phase": self.phase.value,
            "winning_strategy": self.winning_strategy.model_dump() if self.winning_strategy else None,
            "scorecards": [s.model_dump() for s in self.scorecards],
            "positions": self.positions.model_dump(),
            "tick_count": self.tick_count,
        }

    @workflow.run
    async def run(self, inp: AgentInput) -> dict:
        await self._phase_1_discover(inp)
        if not self._stop:
            await self._phase_2_trade(inp)
        return {"stopped": True, "ticks": self.tick_count}

    # ───────────────────────── Phase 1: Discover ─────────────────────────
    async def _phase_1_discover(self, inp: AgentInput) -> None:
        """Fan out N sandboxed backtests, deterministically pick the winner, persist."""
        self.phase = Phase.SYNTHESIZING
        await self._emit("phase_change", {"phase": self.phase.value})

        data_ref = await workflow.execute_activity(
            fetch_historical_data, args=[inp.ticker, inp.history_range], **_T_LONG
        )
        await self._emit("backtest_progress",
                         {"status": "starting_fanout", "n": len(inp.candidate_strategies)})

        wf_id = workflow.info().workflow_id
        handles = await asyncio.gather(*[
            workflow.start_child_workflow(
                BacktestSandboxWorkflow.run,
                BacktestInput(strategy_spec=s, historical_data_ref=data_ref,
                              sandbox_image=settings.sandbox_image),
                id=f"{wf_id}-bt-{s.id}",
            )
            for s in inp.candidate_strategies
        ])
        results = await asyncio.gather(*handles, return_exceptions=True)
        self.scorecards = [r for r in results if isinstance(r, Scorecard)]

        for sc in self.scorecards:
            await self._emit("backtest_progress", {
                "status": "done", "strategy_id": sc.strategy_id,
                "sharpe": sc.sharpe, "roi": sc.roi, "max_drawdown": sc.max_drawdown,
                "error": sc.error, "generated_code": sc.generated_code,
            })

        try:
            winner_card = select_winner(self.scorecards)
        except ValueError as e:
            await self._fail_phase_1(e)

        self.winning_strategy = next(s for s in inp.candidate_strategies
                                     if s.id == winner_card.strategy_id)
        await workflow.execute_activity(persist_strategy, self.winning_strategy, **_T_SHORT)
        await self._emit("phase_change", {
            "phase": "WINNER_SELECTED",
            "winning_strategy": self.winning_strategy.model_dump(),
            "winning_scorecard": winner_card.model_dump(),
        })

    async def _fail_phase_1(self, err: Exception) -> None:
        errors = [sc.error for sc in self.scorecards if sc.error]
        await self._emit("phase_change",
                         {"phase": "FAILED", "reason": str(err), "backtest_errors": errors[:8]})
        raise ApplicationError(
            f"Phase 1 failed: {err}. First backtest error: {errors[0] if errors else 'unknown'}",
            type="Phase1Failed", non_retryable=True,
        )

    # ───────────────────────── Phase 2: Trade ─────────────────────────
    async def _phase_2_trade(self, inp: AgentInput) -> None:
        """Tick loop: fetch context → run Agent → risk check → (approval) → place order."""
        self.phase = Phase.WATCHING
        await self._emit("phase_change", {"phase": self.phase.value})

        while not self._stop:
            await self._wait_for_tick(inp.tick_seconds)
            if self._stop:
                return
            self.tick_count += 1

            market, news = await self._fetch_context(inp.ticker)
            intent = await self._run_trade_agent(market, news)
            # Stamp a deterministic, workflow-controlled id so the UI can identify each
            # tick's intent uniquely. The LLM picks intent.id otherwise and tends to repeat
            # values across ticks, which shadows newer approval requests in the UI.
            intent.id = f"{workflow.info().workflow_id}-t{self.tick_count}"
            await self._emit("trade_intent", {
                "tick": self.tick_count, "intent": intent.model_dump(),
                "price": market.price, "sentiment": news.sentiment,
            })

            if intent.action == TradeAction.HOLD:
                continue

            risk = await workflow.execute_activity(
                risk_check,
                RiskCheckInput(intent=intent, news=news, positions=self.positions,
                               limits=inp.limits, approval_threshold=inp.approval_threshold),
                start_to_close_timeout=timedelta(seconds=5),
            )
            await self._emit("risk_decision",
                             {"trade_id": intent.id, "decision": risk.decision.value,
                              "reason": risk.reason})

            if risk.decision == RiskDecision.BLOCK:
                continue
            if risk.decision == RiskDecision.ALLOW_REQUIRES_APPROVAL:
                if not await self._await_approval(intent, risk, news):
                    continue

            await self._execute_trade(intent)

    async def _wait_for_tick(self, seconds: int) -> None:
        """Sleep `seconds`, or wake immediately on `fast_forward_tick` / `stop`."""
        try:
            await workflow.wait_condition(
                lambda: self._fast_forward or self._stop,
                timeout=timedelta(seconds=seconds),
            )
        except TimeoutError:
            pass
        self._fast_forward = False

    async def _fetch_context(self, ticker: str) -> tuple[MarketSnapshot, NewsSnapshot]:
        """Pull market + news for the current tick, apply any chaos injection."""
        market = await workflow.execute_activity(fetch_market_snapshot, ticker, **_T_MEDIUM)
        news = await workflow.execute_activity(fetch_news_snapshot, ticker, **_T_MEDIUM)
        if self._chaos_news.apply(news):
            await self._emit("chaos", {
                "kind": "bad_news_applied", "tick": self.tick_count,
                "sentiment_applied": news.sentiment, "ttl_remaining": self._chaos_news.ttl,
            })
        return market, news

    async def _await_approval(self, intent: TradeIntent, risk, news: NewsSnapshot) -> bool:
        """Pause for human approval. Returns True if approved, False if rejected/stopped."""
        self.phase = Phase.AWAITING_APPROVAL
        await self._emit("approval_request", {
            "trade_id": intent.id, "intent": intent.model_dump(),
            "risk": risk.model_dump(), "news_sentiment": news.sentiment,
            "headlines": [h.model_dump() for h in news.headlines[:3]],
        })
        await workflow.wait_condition(lambda: intent.id in self._approvals or self._stop)
        self.phase = Phase.WATCHING
        if self._stop or not self._approvals[intent.id]:
            await self._emit("audit", {"trade_id": intent.id, "outcome": "rejected"})
            return False
        return True

    async def _execute_trade(self, intent: TradeIntent) -> None:
        """Place the order via the broker activity, persist the trade, update positions."""
        wf_id = workflow.info().workflow_id
        order = await workflow.execute_activity(
            place_order,
            PlaceOrderInput(intent=intent, idempotency_key=f"{wf_id}:{intent.id}"),
            **_T_MEDIUM,
        )
        await workflow.execute_activity(write_trade_record, order, **_T_SHORT)
        self.positions.apply(order)
        await self._emit("order_placed", {"order": order.model_dump()})

    # ───────────────────────── The OpenAI Agent ─────────────────────────
    async def _run_trade_agent(self, market: MarketSnapshot, news: NewsSnapshot) -> TradeIntent:
        """The agentic step — where the OpenAI Agents SDK meets Temporal.

        Three integration points to notice during the walkthrough:

          1. `Agent(...)` is plain OpenAI Agents SDK — no Temporal-specific code.
             The same constructor you'd use in a standalone script.

          2. `activity_as_tool(...)` is the bridge for tools. The Agent thinks
             it has a normal function tool, but every invocation actually
             dispatches a Temporal activity — durable, retried, in event history.

          3. `Runner.run(...)` looks like a normal in-process agent loop, but the
             OpenAIAgentsPlugin transparently dispatches each LLM call as a
             Temporal activity. If the worker dies between turn 3 and turn 4,
             Temporal replays the workflow and only re-dispatches turn 4 —
             previous turns' LLM responses are recovered from event history.

        `output_type=TradeIntent` makes the SDK enforce a Pydantic schema on the
        final response, so the workflow never parses raw JSON from the model.
        """
        agent = Agent(
            name="TradeIntentAgent",
            instructions=LIVE_AGENT_PROMPT,
            model=settings.openai_model,
            tools=[
                # Wrap two Temporal activities as Agent tools. The Agent calls them
                # like normal functions; under the hood each call becomes a Temporal
                # activity execution recorded in workflow history.
                temporal_agents.workflow.activity_as_tool(fetch_market_snapshot, **_T_MEDIUM),
                temporal_agents.workflow.activity_as_tool(fetch_news_snapshot, **_T_MEDIUM),
            ],
            output_type=TradeIntent,
        )
        input_msg = self._build_agent_input(market, news)
        # Each LLM turn inside Runner.run is its own Temporal activity, so the
        # full multi-turn reasoning loop is durable end-to-end.
        result = await Runner.run(agent, input=input_msg, max_turns=20)
        return result.final_output_as(TradeIntent)

    def _build_agent_input(self, market: MarketSnapshot, news: NewsSnapshot) -> str:
        s = self.winning_strategy
        return (
            f"Ticker: {market.ticker}\n"
            f"Price: {market.price:.2f}\n"
            f"Indicators: RSI={market.rsi:.1f}, MACD={market.macd:.2f}, "
            f"EMA12={market.ema12:.2f}, EMA26={market.ema26:.2f}, "
            f"BB=[{market.bb_lower:.2f}, {market.bb_upper:.2f}]\n"
            f"News sentiment: {news.sentiment:.2f}\n"
            f"Recent headlines: {[h.title for h in news.headlines[:3]]}\n"
            f"Active strategy: {s.family} ({s.id}) params={s.params}\n"
            f"Current positions: {self.positions.model_dump()}\n\n"
            "Decide BUY, SELL, or HOLD with a qty (max 100 shares). The data above is "
            "fresh — return a TradeIntent now without calling tools. Only call "
            "`fetch_market_snapshot` or `fetch_news_snapshot` if a field above is missing."
        )

    # ───────────────────────── UI event bus ─────────────────────────
    async def _emit(self, kind: str, payload: dict) -> None:
        event = UIEvent(ts=workflow.now(), workflow_id=workflow.info().workflow_id,
                        kind=kind, payload=payload)
        await workflow.execute_activity(notify_ui, event, **_T_SHORT)
