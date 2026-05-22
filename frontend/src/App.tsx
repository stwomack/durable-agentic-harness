import { useEffect, useState } from "react";
import { MissionControl } from "./components/MissionControl";
import { EventLog } from "./components/EventLog";
import { WarRoom } from "./components/WarRoom";
import { TradingFloor } from "./components/TradingFloor";
import { ApprovalModal } from "./components/ApprovalModal";
import { ChaosPanel } from "./components/ChaosPanel";
import { useSSE } from "./hooks/useSSE";
import { useWorkflow } from "./hooks/useWorkflow";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [dismissedApprovals, setDismissedApprovals] = useState<Set<string>>(new Set());

  // On mount, auto-attach to the most recent run so a page refresh (or starting
  // the workflow via curl/Temporal CLI) doesn't leave the UI with no SSE subscription.
  useEffect(() => {
    if (workflowId) return;
    fetch("/api/runs/")
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: { workflow_id: string }[]) => {
        const latest = rows?.[0]?.workflow_id;
        if (latest && latest !== "-" && !latest.startsWith("hello-")) {
          setWorkflowId(latest);
        }
      })
      .catch(() => {});
  }, [workflowId]);
  const expected = 8;
  const events = useSSE(workflowId);
  const { phase, scorecards, winningStrategy, ticks, trades, pendingApproval } = useWorkflow(events);

  const showApproval = workflowId && pendingApproval && !dismissedApprovals.has(pendingApproval.trade_id);

  return (
    <div className="min-h-screen p-10 max-w-6xl mx-auto space-y-8">
      <header className="flex items-baseline justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">
          <span className="text-accent">Durable</span> Agentic Harness
        </h1>
        <span className="text-xs font-mono text-foreground/50 flex items-center gap-2">
          {workflowId ?? "no active run"}
          {workflowId && (
            <button
              onClick={() => setWorkflowId(null)}
              className="text-foreground/40 hover:text-rose-300"
              title="detach from this run"
            >
              ✕
            </button>
          )}
        </span>
      </header>
      <MissionControl workflowId={workflowId} onStart={setWorkflowId} currentPhase={phase} />
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">War Room</h2>
        <WarRoom scorecards={scorecards} winningStrategy={winningStrategy} expected={expected} />
      </section>
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">Trading Floor</h2>
        <TradingFloor ticks={ticks} trades={trades} />
      </section>
      <EventLog events={events} />
      <ChaosPanel workflowId={workflowId} />
      {showApproval && pendingApproval && (
        <ApprovalModal
          workflowId={workflowId!}
          request={pendingApproval}
          onClose={() => setDismissedApprovals((s: Set<string>) => new Set([...s, pendingApproval.trade_id]))}
        />
      )}
    </div>
  );
}
