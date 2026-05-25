// v2 chaos surface: Kill/Restart Worker, Fast Forward, Inject Bad News.
// Removed in v2: crashBroker, restartBroker (Mockoon runs on the host via
// Mockoon Desktop, not in compose).
export function useChaos(workflowId: string | null) {
  async function call(path: string, body?: object) {
    await fetch(`/api/chaos/${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }
  return {
    killWorker: async () => { await call("kill_worker"); },
    restartWorker: async () => { await call("restart_worker"); },
    fastForward: async () => {
      if (!workflowId) return;
      await call("fast_forward", { workflow_id: workflowId });
    },
    injectBadNews: async () => {
      if (!workflowId) return;
      // Stays clear of RESTRICTED_NEWS_TERMS in shared/constants.py so the SELL
      // is allowed through risk_check (sentiment also above -0.5 block threshold).
      // Demo shows the agent reacting to bad news with a SELL, not getting blocked.
      await call("inject_news", {
        workflow_id: workflowId,
        headline: "Tech sector sees broad sell-off; analysts cut NVDA price target",
        sentiment: -0.4,
      });
    },
  };
}
