const API = ""; // proxied by Vite

export async function startRun(payload: { ticker: string; num_sandboxes?: number }) {
  const r = await fetch(`${API}/api/runs/`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { workflow_id: string; ticker: string };
}

export async function getState(workflowId: string) {
  const r = await fetch(`${API}/api/runs/${workflowId}/state`);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

export async function terminateRun(workflowId: string, reason?: string) {
  const r = await fetch(`${API}/api/runs/${workflowId}/terminate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ reason: reason ?? null }),
  });
  if (!r.ok) throw new Error(await r.text());
  return (await r.json()) as { ok: boolean; workflow_id: string; reason: string };
}
