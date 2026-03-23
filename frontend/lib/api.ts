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

export async function fetchSimulation(date: string, eventName?: string) {
  const q = new URLSearchParams({ date });
  if (eventName) q.set("event_name", eventName);
  const r = await fetch(`${BASE}/zones/simulate?${q}`, { cache: "no-store" });
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

export async function fetchHistory(zoneId: string, limit = 48) {
  const r = await fetch(`${BASE}/zones/${zoneId}/history?limit=${limit}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/zones/${zoneId}/history ${r.status}`);
  return r.json();
}

export async function fetchImpactReport(params: {
  start: string; end: string;
  baseline_start?: string; baseline_end?: string;
}) {
  const q = new URLSearchParams({ start: params.start, end: params.end });
  if (params.baseline_start) q.set("baseline_start", params.baseline_start);
  if (params.baseline_end) q.set("baseline_end", params.baseline_end);
  const r = await fetch(`${BASE}/reports/impact?${q}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/reports/impact ${r.status}`);
  return r.json();
}

export async function fetchEventImpact(eventName: string) {
  const r = await fetch(`${BASE}/reports/impact/event/${encodeURIComponent(eventName)}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/reports/impact/event ${r.status}`);
  return r.json();
}

export async function fetchEvents() {
  const r = await fetch(`${BASE}/reports/events`, { next: { revalidate: 3600 } });
  if (!r.ok) throw new Error(`/reports/events ${r.status}`);
  return r.json();
}

export async function fetchPreEventReport(eventName: string, date?: string) {
  const q = new URLSearchParams();
  if (date) q.set("date", date);
  const qs = q.toString() ? `?${q}` : "";
  const r = await fetch(`${BASE}/reports/pre-event/${encodeURIComponent(eventName)}${qs}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/reports/pre-event ${r.status}`);
  return r.json();
}

export async function fetchForecastAccuracy(params?: { zone_id?: string; horizon?: string; since?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.zone_id) q.set("zone_id", params.zone_id);
  if (params?.horizon) q.set("horizon", params.horizon);
  if (params?.since)   q.set("since", params.since);
  if (params?.limit)   q.set("limit", String(params.limit));
  const r = await fetch(`${BASE}/zones/forecast/accuracy?${q}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`/zones/forecast/accuracy ${r.status}`);
  return r.json();
}

export async function submitContact(payload: {
  nom: string;
  email: string;
  organisation: string;
  message: string;
  source?: string;
}) {
  const r = await fetch(`${BASE}/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`/contact ${r.status}`);
  return r.json();
}
