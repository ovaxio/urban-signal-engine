// ── Scoring utilities — single source of truth ──────────────────────────────

export function scoreColor(s: number): string {
  if (s < 35) return "#22c55e";
  if (s < 55) return "#eab308";
  if (s < 72) return "#f97316";
  return "#ef4444";
}

export function scoreLevel(s: number): string {
  if (s < 35) return "CALME";
  if (s < 55) return "MODÉRÉ";
  if (s < 72) return "TENDU";
  return "CRITIQUE";
}

export function scoreToRadius(score: number): number {
  return 18 + (score / 100) * 22;
}
