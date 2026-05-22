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
        workflow_id: workflowId,
        headline: "SEC probe into NVDA announced overnight",
        sentiment: -0.85,
      }),
  };
}
