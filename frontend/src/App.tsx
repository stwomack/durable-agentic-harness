import { useEffect, useState } from "react";
import { MissionControl } from "./components/MissionControl";
import { EventLog } from "./components/EventLog";
import { WarRoom } from "./components/WarRoom";
import { TradingFloor } from "./components/TradingFloor";
import { ApprovalModal } from "./components/ApprovalModal";
import { ChaosPanel } from "./components/ChaosPanel";
import { useSSE } from "./hooks/useSSE";
import { useWorkflow } from "./hooks/useWorkflow";

export type DurabilityState = "idle" | "down" | "recovered";

export default function App() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [dismissedApprovals, setDismissedApprovals] = useState<Set<string>>(new Set());
  const [durability, setDurability] = useState<DurabilityState>("idle");

  // Auto-clear the "recovered" banner after 12s so the stage returns to a clean state.
  useEffect(() => {
    if (durability !== "recovered") return;
    const t = setTimeout(() => setDurability("idle"), 12_000);
    return () => clearTimeout(t);
  }, [durability]);

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
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            <span className="text-accent">Durable</span> Agentic Harness
          </h1>
          <p className="text-xs text-foreground/60 mt-1">
            <span className="text-accent-violet">OpenAI Agents SDK</span> trade-intent loop,
            made durable by <span className="text-accent">Temporal</span>.
          </p>
        </div>
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
      {durability !== "idle" && (
        <div className={"border rounded px-4 py-3 text-sm " +
          (durability === "down"
            ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
            : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200")}>
          {durability === "down" ? (
            <>
              <span className="font-semibold">Worker down.</span>{" "}
              Workflow paused mid-tool-call. Temporal will replay event history from the last
              completed event when the worker comes back.
            </>
          ) : (
            <>
              <span className="font-semibold">Worker up.</span>{" "}
              Temporal replayed event history and resumed the Agent loop from the exact
              event it was on — no lost state, no retry from scratch.
            </>
          )}
        </div>
      )}
      <MissionControl workflowId={workflowId} onStart={setWorkflowId} currentPhase={phase} />
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">
          War Room
          <span className="ml-2 normal-case tracking-normal text-foreground/40 text-xs">
            · parallel sandboxed backtests, orchestrated as Temporal child workflows
          </span>
        </h2>
        <WarRoom scorecards={scorecards} winningStrategy={winningStrategy} expected={expected} />
      </section>
      <section>
        <h2 className="text-sm uppercase tracking-widest text-foreground/60 mb-3">
          Trading Floor
          <span className="ml-2 normal-case tracking-normal text-foreground/40 text-xs">
            · <span className="text-accent-violet">OpenAI Agents SDK</span> Agent + Runner →
            tools via Temporal activities
          </span>
        </h2>
        <TradingFloor ticks={ticks} trades={trades} />
      </section>
      <EventLog events={events} />
      <ChaosPanel workflowId={workflowId} onDurabilityChange={setDurability} />
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
