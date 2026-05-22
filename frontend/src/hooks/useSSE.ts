import { useEffect, useState } from "react";
import type { UIEvent } from "../types";

// Bypass the Vite dev proxy for SSE — http-proxy buffers streamed responses
// which breaks EventSource. FastAPI's CORS allows :5173 directly.
// Override at runtime with VITE_SSE_BASE if needed (e.g. when deployed).
const SSE_BASE = (import.meta as any).env?.VITE_SSE_BASE || "http://localhost:8000";

export function useSSE(workflowId: string | null) {
  const [events, setEvents] = useState<UIEvent[]>([]);
  useEffect(() => {
    // Whenever the workflow changes (including detach), wipe stale events.
    setEvents([]);
    if (!workflowId) return;
    const es = new EventSource(`${SSE_BASE}/api/runs/${workflowId}/events`);
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
