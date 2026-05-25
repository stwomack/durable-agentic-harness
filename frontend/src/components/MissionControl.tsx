import { useState } from "react";
import { startRun } from "../lib/api";

const PHASES = ["SYNTHESIZING", "WINNER_SELECTED", "WATCHING", "AWAITING_APPROVAL"];

export function MissionControl({
  workflowId, onStart, currentPhase,
}: {
  workflowId: string | null;
  currentPhase: string;
  onStart: (wfId: string) => void;
}) {
  const [ticker, setTicker] = useState("NVDA");
  const [busy, setBusy] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <input
          className="bg-card border border-border rounded px-3 py-2 font-mono uppercase w-32"
          value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())}
        />
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await startRun({ ticker });
              onStart(r.workflow_id);
            } catch (e: any) {
              console.error("startRun failed:", e);
              alert("startRun failed: " + (e?.message || String(e)));
            } finally { setBusy(false); }
          }}
          className="bg-accent text-background font-medium rounded px-4 py-2 hover:opacity-90 disabled:opacity-40"
        >
          {busy ? "Starting..." : (workflowId ? "Start New Run" : "Start Self-Evolving Agent")}
        </button>
        {workflowId && (
          <a href={`http://localhost:8233/namespaces/default/workflows/${workflowId}`}
             target="_blank" rel="noreferrer"
             className="text-xs underline text-accent-violet">View in Temporal UI</a>
        )}
      </div>

      <div className="flex gap-3">
        {PHASES.map((p) => (
          <div key={p}
               className={"px-3 py-1 rounded border text-xs font-mono " +
                          (p === currentPhase ? "bg-accent text-background border-accent" : "border-border text-foreground/60")}>
            {p}
          </div>
        ))}
      </div>
    </div>
  );
}
