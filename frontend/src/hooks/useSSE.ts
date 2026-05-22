import { useEffect, useState } from "react";
import type { UIEvent } from "../types";

export function useSSE(workflowId: string | null) {
  const [events, setEvents] = useState<UIEvent[]>([]);
  useEffect(() => {
    if (!workflowId) return;
    const es = new EventSource(`/api/runs/${workflowId}/events`);
    es.onmessage = (m) => {
      try {
        const data = JSON.parse(m.data) as UIEvent;
        setEvents((prev) => [...prev, data]);
      } catch {}
    };
    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as UIEvent;
        setEvents((prev) => [...prev, data]);
      } catch {}
    };
    ["phase_change", "backtest_progress", "trade_intent", "risk_decision",
     "approval_request", "order_placed", "drift_detected", "audit", "chaos"]
      .forEach((k) => es.addEventListener(k, handler));
    return () => es.close();
  }, [workflowId]);
  return events;
}
