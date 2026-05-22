import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.constants import DRIFT_CHECK_TICK_INTERVAL, Phase, RiskDecision, TradeAction
    from shared.models import (
        AgentInput, AgentCallInput, BacktestInput, DriftInput, DriftResult,
        NewsHeadline, PlaceOrderInput, Positions, RiskCheckInput, Scorecard,
        StrategySpec, UIEvent,
    )
    from worker.activities.drift import check_drift
    from shared.selection import select_winner
    from worker.workflows.backtest import BacktestSandboxWorkflow
    from worker.activities.market import fetch_historical_data, fetch_market_snapshot
    from worker.activities.news import fetch_news_snapshot
    from worker.activities.llm import call_agent
    from worker.activities.risk import risk_check
    from worker.activities.broker import place_order
    from worker.activities.persist import persist_strategy, write_trade_record
    from worker.activities.ui import notify_ui


@workflow.defn
class SelfEvolvingStockAgentWorkflow:
    def __init__(self) -> None:
        self.phase: Phase = Phase.SYNTHESIZING
        self.winning_strategy: Optional[StrategySpec] = None
        self.scorecards: list[Scorecard] = []
        self.positions: Positions = Positions()
        self.tick_count: int = 0
        self.live_roi: float = 0.0
        self._approvals: dict[str, bool] = {}
        self._injected_news: list[NewsHeadline] = []
        self._injected_sentiment_override: Optional[float] = None
        self._fast_forward: bool = False
        self._stop: bool = False
        self._force_drift: bool = False

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
        self._injected_news.append(NewsHeadline(title=headline, published_at=0))
        self._injected_sentiment_override = sentiment

    @workflow.signal
    def force_drift(self) -> None:
        self._force_drift = True

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
            "live_roi": self.live_roi,
        }

    @workflow.run
    async def run(self, inp: AgentInput) -> dict:
        wf_id = workflow.info().workflow_id

        while not self._stop:
            await self._run_phase_1(inp, wf_id)
            if self._stop:
                break
            drifted = await self._run_phases_2_and_3(inp, wf_id)
            if not drifted:
                break
        return {"stopped": True, "ticks": self.tick_count}

    async def _run_phase_1(self, inp: AgentInput, wf_id: str) -> None:
        self.phase = Phase.SYNTHESIZING
        await self._emit(wf_id, "phase_change", {"phase": self.phase.value})

        data_ref = await workflow.execute_activity(
            fetch_historical_data, args=[inp.ticker, inp.history_range],
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        await self._emit(wf_id, "backtest_progress",
                         {"status": "starting_fanout", "n": len(inp.candidate_strategies)})

        child_handles = await asyncio.gather(*[
            workflow.start_child_workflow(
                BacktestSandboxWorkflow.run,
                BacktestInput(strategy_spec=s, historical_data_ref=data_ref,
                              sandbox_image="durable-agent-sandbox:latest"),
                id=f"{wf_id}-bt-{s.id}-{self.tick_count}",
            )
            for s in inp.candidate_strategies
        ])
        results = await asyncio.gather(*child_handles, return_exceptions=True)
        self.scorecards = [r for r in results if isinstance(r, Scorecard)]

        for sc in self.scorecards:
            await self._emit(wf_id, "backtest_progress", {
                "status": "done", "strategy_id": sc.strategy_id,
                "sharpe": sc.sharpe, "roi": sc.roi, "max_drawdown": sc.max_drawdown,
                "error": sc.error, "generated_code": sc.generated_code,
            })

        winner = select_winner(self.scorecards)
        winner_spec = next(s for s in inp.candidate_strategies if s.id == winner.strategy_id)
        self.winning_strategy = winner_spec
        self.live_roi = 0.0
        await workflow.execute_activity(
            persist_strategy, winner_spec,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        await self._emit(wf_id, "phase_change",
                         {"phase": "WINNER_SELECTED",
                          "winning_strategy": winner_spec.model_dump(),
                          "winning_scorecard": winner.model_dump()})

    async def _run_phases_2_and_3(self, inp: AgentInput, wf_id: str) -> bool:
        """Returns True if drift triggered re-synthesis, False if stop requested or graceful exit."""
        self.phase = Phase.WATCHING
        await self._emit(wf_id, "phase_change", {"phase": self.phase.value})

        while not self._stop:
            try:
                await workflow.wait_condition(
                    lambda: self._fast_forward or self._stop or self._force_drift,
                    timeout=timedelta(seconds=inp.tick_seconds),
                )
            except TimeoutError:
                pass
            self._fast_forward = False
            if self._stop:
                return False
            if self._force_drift:
                self._force_drift = False
                await self._emit(wf_id, "drift_detected", {"reason": "forced by chaos"})
                self.phase = Phase.EVOLVING
                await self._emit(wf_id, "phase_change", {"phase": self.phase.value})
                return True

            self.tick_count += 1
            market = await workflow.execute_activity(
                fetch_market_snapshot, inp.ticker,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            news = await workflow.execute_activity(
                fetch_news_snapshot, inp.ticker,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            if self._injected_news:
                news.headlines.extend(self._injected_news)
                self._injected_news = []
            if self._injected_sentiment_override is not None:
                news.sentiment = self._injected_sentiment_override
                self._injected_sentiment_override = None

            intent = await workflow.execute_activity(
                call_agent,
                AgentCallInput(winning_strategy=self.winning_strategy, market=market,
                               news=news, positions=self.positions),
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            await self._emit(wf_id, "trade_intent", {
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
            await self._emit(wf_id, "risk_decision",
                             {"trade_id": intent.id, "decision": risk.decision.value, "reason": risk.reason})

            if risk.decision == RiskDecision.BLOCK:
                continue

            if risk.decision == RiskDecision.ALLOW_REQUIRES_APPROVAL:
                self.phase = Phase.AWAITING_APPROVAL
                await self._emit(wf_id, "approval_request", {
                    "trade_id": intent.id, "intent": intent.model_dump(),
                    "risk": risk.model_dump(), "news_sentiment": news.sentiment,
                    "headlines": [h.model_dump() for h in news.headlines][:3],
                })
                await workflow.wait_condition(lambda: intent.id in self._approvals or self._stop)
                self.phase = Phase.WATCHING
                if self._stop:
                    return False
                if not self._approvals[intent.id]:
                    await self._emit(wf_id, "audit", {"trade_id": intent.id, "outcome": "rejected"})
                    continue

            order = await workflow.execute_activity(
                place_order,
                PlaceOrderInput(intent=intent, idempotency_key=f"{wf_id}:{intent.id}"),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            await workflow.execute_activity(
                write_trade_record, order,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            self.positions.apply(order)
            self.live_roi += 0.005 if intent.action == TradeAction.BUY else -0.002
            await self._emit(wf_id, "order_placed", {"order": order.model_dump()})

            # ───── PHASE 4 drift check (every K ticks) ─────
            if self.tick_count % DRIFT_CHECK_TICK_INTERVAL == 0 and self.winning_strategy is not None:
                baseline_roi = next(
                    (s.roi for s in self.scorecards if s.strategy_id == self.winning_strategy.id),
                    0.0,
                )
                drift = await workflow.execute_activity(
                    check_drift,
                    DriftInput(baseline_sharpe=0.0, live_roi=self.live_roi,
                               backtest_roi=baseline_roi, threshold=inp.drift_threshold),
                    start_to_close_timeout=timedelta(seconds=5),
                )
                if drift.drifted:
                    await self._emit(wf_id, "drift_detected", {"reason": drift.reason})
                    self.phase = Phase.EVOLVING
                    await self._emit(wf_id, "phase_change", {"phase": self.phase.value})
                    return True

        return False

    async def _emit(self, wf_id: str, kind: str, payload: dict) -> None:
        event = UIEvent(ts=workflow.now(), workflow_id=wf_id, kind=kind, payload=payload)
        await workflow.execute_activity(
            notify_ui, event,
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
