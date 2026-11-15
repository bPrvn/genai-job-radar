// Loads dashboard data. Live mode: the local backend (status edits, Run now).
// Snapshot mode: the JSON published with the site (read-only).
export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function withTimeout(url, ms, opts = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctrl.signal });
  } finally {
    clearTimeout(t);
  }
}

export async function loadData() {
  try {
    const r = await withTimeout(`${API}/api/snapshot`, 1500);
    if (r.ok) return await r.json();
  } catch {
    /* backend not running: fall back to the published snapshot */
  }
  const r = await fetch(`./data/snapshot.json?t=${Date.now()}`);
  if (!r.ok) throw new Error("No snapshot published yet. Run the backend once: python -m radar run");
  return { ...(await r.json()), live: false };
}

async function send(path, method, body) {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

export const setJob = (id, patch) => send(`/api/jobs/${encodeURIComponent(id)}`, "PATCH", patch);
export const setPracticed = (id, practiced) => send(`/api/questions/${id}`, "PATCH", { practiced });
export const runNow = () => send(`/api/run`, "POST");
export const health = () => withTimeout(`${API}/api/health`, 1500).then((r) => r.json());
