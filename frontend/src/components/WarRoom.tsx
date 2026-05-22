import { useState } from "react";
import type { Scorecard, StrategySpec } from "../types";

type Props = {
  scorecards: Record<string, Scorecard>;
  winningStrategy: StrategySpec | null;
  expected: number;
};

export function WarRoom({ scorecards, winningStrategy, expected }: Props) {
  const cards = Object.values(scorecards);
  const placeholders = Math.max(0, expected - cards.length);
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map((sc) => (
        <SandboxCard key={sc.strategy_id} sc={sc} winning={sc.strategy_id === winningStrategy?.id} />
      ))}
      {Array.from({ length: placeholders }).map((_, i) => (
        <div key={`p-${i}`}
             className="border border-border rounded p-4 h-40 animate-pulse bg-card/50 text-xs text-foreground/40 font-mono">
          running…
        </div>
      ))}
    </div>
  );
}

function SandboxCard({ sc, winning }: { sc: Scorecard; winning: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={"border rounded p-4 bg-card transition-all " +
                    (winning ? "border-accent shadow-[0_0_30px_-5px_hsl(189_90%_55%/0.6)]" : "border-border")}>
      <div className="flex items-baseline justify-between">
        <div className="font-mono text-xs">{sc.strategy_id}</div>
        {winning && <span className="text-[10px] font-bold text-accent uppercase">WINNER</span>}
      </div>
      {sc.error ? (
        <div className="mt-3 text-rose-300 text-xs font-mono">error: {sc.error}</div>
      ) : (
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs font-mono">
          <Metric label="Sharpe" value={sc.sharpe.toFixed(2)} />
          <Metric label="ROI" value={(sc.roi * 100).toFixed(1) + "%"} />
          <Metric label="DD" value={(sc.max_drawdown * 100).toFixed(1) + "%"} />
        </div>
      )}
      <button onClick={() => setOpen((o) => !o)}
              className="mt-3 text-[10px] underline text-accent-violet">
        {open ? "hide" : "show"} generated code
      </button>
      {open && (
        <pre className="mt-2 max-h-40 overflow-auto text-[10px] bg-background/60 p-2 rounded">
{sc.generated_code || "(no code)"}
        </pre>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-foreground/40 text-[10px] uppercase">{label}</div>
      <div className="text-foreground">{value}</div>
    </div>
  );
}
