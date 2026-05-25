import type { UIEvent } from "../types";

const KIND_COLORS: Record<string, string> = {
  phase_change: "text-cyan-300",
  backtest_progress: "text-violet-300",
  trade_intent: "text-amber-300",
  risk_decision: "text-orange-300",
  approval_request: "text-yellow-300",
  order_placed: "text-emerald-300",
  chaos: "text-pink-400",
  audit: "text-foreground/60",
};

export function EventLog({ events }: { events: UIEvent[] }) {
  return (
    <div className="font-mono text-xs h-72 overflow-auto rounded border border-border bg-card p-3">
      {events.length === 0 && <div className="text-foreground/40">awaiting events…</div>}
      {events.map((e, i) => (
        <div key={i} className="flex gap-2">
          <span className="text-foreground/40">{new Date(e.ts).toLocaleTimeString()}</span>
          <span className={KIND_COLORS[e.kind] ?? "text-foreground/80"}>{e.kind}</span>
          <span className="text-foreground/70 truncate">{JSON.stringify(e.payload)}</span>
        </div>
      ))}
    </div>
  );
}
