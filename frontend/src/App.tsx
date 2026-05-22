import { useState } from "react";
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
        <span className="text-xs font-mono text-foreground/50">{workflowId ?? "no active run"}</span>
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
