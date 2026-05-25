import { useChaos } from "../hooks/useChaos";
import type { DurabilityState } from "../App";

export function ChaosPanel({
  workflowId,
  onDurabilityChange,
}: {
  workflowId: string | null;
  onDurabilityChange?: (s: DurabilityState) => void;
}) {
  const c = useChaos(workflowId);
  const Btn = ({ label, onClick, variant }: { label: string; onClick: () => void | Promise<void>; variant: "danger" | "warn" | "info" }) => (
    <button
      onClick={onClick}
      className={"text-xs font-mono uppercase tracking-wider rounded px-2 py-1 transition-all " +
                 (variant === "danger" ? "bg-rose-500/20 text-rose-200 hover:bg-rose-500/40" :
                  variant === "warn" ? "bg-amber-500/20 text-amber-200 hover:bg-amber-500/40" :
                  "bg-accent/20 text-accent hover:bg-accent/40")}
    >
      {label}
    </button>
  );
  return (
    <div className="fixed right-6 top-1/2 -translate-y-1/2 w-44 space-y-2 z-40 bg-card border border-border rounded p-3">
      <div className="text-[10px] uppercase tracking-widest text-foreground/50 mb-1">
        Temporal Durability · Chaos
      </div>
      <div className="flex flex-col gap-2">
        <Btn label="Kill Worker"
             onClick={async () => { onDurabilityChange?.("down"); await c.killWorker(); }}
             variant="danger" />
        <Btn label="Restart Worker"
             onClick={async () => { await c.restartWorker(); onDurabilityChange?.("recovered"); }}
             variant="info" />
        <Btn label="Inject Bad News" onClick={c.injectBadNews} variant="warn" />
        <Btn label="Fast Forward"    onClick={c.fastForward}   variant="info" />
      </div>
    </div>
  );
}
