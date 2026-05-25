export type Phase = "SYNTHESIZING" | "WATCHING" | "AWAITING_APPROVAL";

export type StrategySpec = {
  id: string;
  family: "RSI" | "MACD" | "EMA_CROSS" | "BOLLINGER" | "MEAN_REVERSION";
  params: Record<string, number>;
};

export type Scorecard = {
  strategy_id: string;
  roi: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  num_trades: number;
  generated_code: string;
  error?: string | null;
};

export type UIEvent = {
  ts: string;
  workflow_id: string;
  kind: string;
  payload: Record<string, unknown>;
};

export type RunState = {
  phase: Phase | "WINNER_SELECTED";
  winning_strategy: StrategySpec | null;
  scorecards: Scorecard[];
};
