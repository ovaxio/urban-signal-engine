// ── API layer — fetch only, no domain logic ─────────────────────────────────

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function fetchScores(params?: { min_score?: number; level?: string }) {
  const q = new URLSearchParams();
  if (params?.min_score) q.set("min_score", String(params.min_score));
  if (params?.level)     q.set("level", params.level);
  const r = await fetch(`${BASE}/zones/scores?${q}`, { next: { revalidate: 60 } });
  if (!r.ok) throw new Error(`/zones/scores ${r.status}`);
  return r.json();
}

export async function fetchDetail(id: string, init?: RequestInit) {
  const url = new URL(`${BASE}/zones/${id}/detail`);
  const res = await fetch(url.toString(), { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`Failed to fetch zone detail: ${res.status}`);
  return res.json();
}

export async function fetchForecast(id: string, init?: RequestInit) {
  const url = new URL(`${BASE}/zones/${id}/forecast`);
  const res = await fetch(url.toString(), { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`Failed to fetch zone forecast: ${res.status}`);
  return res.json();
}

export async function fetchHealth() {
  const r = await fetch(`${BASE}/health`, { next: { revalidate: 10 } });
  if (!r.ok) throw new Error("health failed");
  return r.json();
}

export async function fetchSimulation(date: string) {
  const r = await fetch(`${BASE}/zones/simulate?date=${date}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/zones/simulate ${r.status}`);
  return r.json();
}

export async function fetchSimulationDetail(id: string, date: string) {
  const r = await fetch(`${BASE}/zones/${id}/simulate-detail?date=${date}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/zones/${id}/simulate-detail ${r.status}`);
  return r.json();
}

export async function fetchAlerts(limit = 20) {
  const r = await fetch(`${BASE}/zones/alerts?limit=${limit}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/zones/alerts ${r.status}`);
  return r.json();
}
