import type { ApprovalReq } from "../hooks/useWorkflow";

export function ApprovalModal({
  workflowId, request, onClose,
}: {
  workflowId: string;
  request: ApprovalReq;
  onClose: () => void;
}) {
  async function send(action: "approve" | "reject") {
    await fetch(`/api/runs/${workflowId}/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ trade_id: request.trade_id }),
    });
    onClose();
  }
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-lg p-6 max-w-md w-full space-y-4 shadow-2xl">
        <div className="text-xs uppercase tracking-widest text-amber-300">Approval Required</div>
        <div className="font-mono text-sm">
          <div className="flex justify-between"><span>Action</span><span className="text-accent">{request.intent.action}</span></div>
          <div className="flex justify-between"><span>Ticker</span><span>{request.intent.ticker}</span></div>
          <div className="flex justify-between"><span>Qty</span><span>{request.intent.qty}</span></div>
          <div className="flex justify-between"><span>Sentiment</span><span>{request.news_sentiment.toFixed(2)}</span></div>
        </div>
        <div className="text-xs text-foreground/70 italic">"{request.intent.rationale}"</div>
        <div className="text-xs text-foreground/60">
          <div className="font-bold mb-1">Risk:</div>
          <div>{request.risk.reason}</div>
        </div>
        <div className="text-xs text-foreground/60">
          <div className="font-bold mb-1">Recent headlines:</div>
          <ul className="list-disc pl-4 space-y-1">
            {request.headlines.map((h, i) => <li key={i}>{h.title}</li>)}
          </ul>
        </div>
        <div className="flex gap-3 pt-2">
          <button onClick={() => send("approve")}
                  className="flex-1 bg-emerald-500 text-background font-bold rounded px-4 py-2 hover:opacity-90">
            Approve
          </button>
          <button onClick={() => send("reject")}
                  className="flex-1 bg-rose-500 text-background font-bold rounded px-4 py-2 hover:opacity-90">
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
