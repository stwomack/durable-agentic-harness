import { useMemo } from "react";
import type { UIEvent, Scorecard, StrategySpec } from "./../types";

export type TickPoint = { tick: number; price: number };
export type Trade = {
  trade_id: string;
  action: string;
  qty: number;
  rationale?: string;
  risk?: { decision: string; reason: string };
  order?: { order_id: string; status: string; filled_qty: number; avg_price: number };
};
export type ApprovalReq = {
  trade_id: string;
  intent: { id: string; ticker: string; action: string; qty: number; rationale: string };
  risk: { decision: string; reason: string };
  news_sentiment: number;
  headlines: { title: string; published_at: number }[];
};

export function useWorkflow(events: UIEvent[]) {
  return useMemo(() => {
    let phase = "SYNTHESIZING" as string;
    const scorecards: Record<string, Scorecard> = {};
    let winningStrategy: StrategySpec | null = null;
    let winningScorecard: Scorecard | null = null;
    const ticks: TickPoint[] = [];
    const trades: Record<string, Trade> = {};
    const approvals: ApprovalReq[] = [];

    for (const e of events) {
      if (e.kind === "phase_change") {
        phase = (e.payload.phase as string) ?? phase;
        if (e.payload.winning_strategy) winningStrategy = e.payload.winning_strategy as StrategySpec;
        if (e.payload.winning_scorecard) winningScorecard = e.payload.winning_scorecard as Scorecard;
      }
      if (e.kind === "backtest_progress" && e.payload.status === "done") {
        const sid = e.payload.strategy_id as string;
        scorecards[sid] = {
          strategy_id: sid,
          roi: (e.payload.roi as number) ?? 0,
          sharpe: (e.payload.sharpe as number) ?? 0,
          max_drawdown: (e.payload.max_drawdown as number) ?? 0,
          win_rate: 0,
          num_trades: 0,
          generated_code: (e.payload.generated_code as string) ?? "",
          error: (e.payload.error as string) ?? null,
        };
      }
      if (e.kind === "trade_intent") {
        const intent = e.payload.intent as Trade & { id: string };
        ticks.push({ tick: e.payload.tick as number, price: e.payload.price as number });
        trades[intent.id] = {
          trade_id: intent.id, action: intent.action, qty: intent.qty,
          rationale: (intent as any).rationale,
        };
      }
      if (e.kind === "risk_decision") {
        const t = trades[e.payload.trade_id as string];
        if (t) t.risk = { decision: e.payload.decision as string, reason: e.payload.reason as string };
      }
      if (e.kind === "approval_request") {
        approvals.push(e.payload as unknown as ApprovalReq);
      }
      if (e.kind === "order_placed") {
        const o = e.payload.order as Trade["order"];
        const recent = Object.values(trades).reverse()[0];
        if (recent && o) recent.order = o;
      }
    }

    const pendingApproval = approvals.find(
      (a) => !trades[a.trade_id]?.order && trades[a.trade_id]?.risk?.decision === "allow_requires_approval",
    );

    return { phase, scorecards, winningStrategy, winningScorecard, ticks, trades, pendingApproval };
  }, [events]);
}
