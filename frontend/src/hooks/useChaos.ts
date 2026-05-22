export function useChaos(workflowId: string | null) {
  async function call(path: string, body?: object) {
    await fetch(`/api/chaos/${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }
  return {
    killWorker: () => call("kill_worker"),
    restartWorker: () => call("restart_worker"),
    crashBroker: () => call("crash_broker"),
    restartBroker: () => call("restart_broker"),
    fastForward: () => workflowId && call("fast_forward", { workflow_id: workflowId }),
    forceDrift: () => workflowId && call("force_drift", { workflow_id: workflowId }),
    injectBadNews: () =>
      workflowId &&
      call("inject_news", {
        // Stays clear of RESTRICTED_NEWS_TERMS in shared/constants.py so the SELL
        // is allowed through risk_check (sentiment also kept above -0.5 block threshold).
        // Demo shows the agent reacting to bad news with a SELL, not getting blocked.
        workflow_id: workflowId,
        headline: "Tech sector sees broad sell-off; analysts cut NVDA price target",
        sentiment: -0.4,
      }),
  };
}
