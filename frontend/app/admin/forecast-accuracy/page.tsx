"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchForecastAccuracy } from "@/lib/api";
import type { ForecastAccuracy, ForecastAccuracyHorizon, ForecastEvaluation } from "@/domain/types";
import AppNav from "@/components/layout/AppNav";

const HORIZONS = ["30min", "60min", "2h", "6h", "12h", "24h"];

const ZONES: { id: string; name: string }[] = [
  { id: "part-dieu",    name: "Part-Dieu" },
  { id: "presquile",    name: "Presqu'île" },
  { id: "vieux-lyon",   name: "Vieux-Lyon" },
  { id: "perrache",     name: "Perrache" },
  { id: "gerland",      name: "Gerland" },
  { id: "guillotiere",  name: "Guillotière" },
  { id: "brotteaux",    name: "Brotteaux" },
  { id: "villette",     name: "La Villette" },
  { id: "montchat",     name: "Montchat" },
  { id: "fourviere",    name: "Fourvière" },
  { id: "croix-rousse", name: "Croix-Rousse" },
  { id: "confluence",   name: "Confluence" },
];

function maeColor(mae: number | null): string {
  if (mae === null) return "var(--text-muted)";
  if (mae <= 5)  return "#22c55e";
  if (mae <= 10) return "#f97316";
  return "#ef4444";
}

function biasLabel(bias: number | null): string {
  if (bias === null) return "-";
  if (bias > 2)  return `+${bias} (sur-estime)`;
  if (bias < -2) return `${bias} (sous-estime)`;
  return `${bias > 0 ? "+" : ""}${bias} (neutre)`;
}

export default function ForecastAccuracyPage() {
  const [data, setData]       = useState<ForecastAccuracy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [zoneFilter, setZoneFilter] = useState("");
  const [horizonFilter, setHorizonFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { limit: 100 };
      if (zoneFilter)    params.zone_id = zoneFilter;
      if (horizonFilter) params.horizon = horizonFilter;
      const res = await fetchForecastAccuracy(params as { zone_id?: string; horizon?: string; limit?: number });
      setData(res);
    } catch {
      setError("Impossible de charger les stats de forecast.");
    } finally {
      setLoading(false);
    }
  }, [zoneFilter, horizonFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex min-h-screen flex-col font-mono">
      <div className="border-b border-border bg-bg-card px-6 py-3.5">
        <div className="mx-auto flex max-w-[960px] items-center justify-between">
          <div>
            <div className="text-sm font-bold text-text-primary">Forecast Accuracy</div>
            <div className="mt-0.5 text-[10px] text-text-muted">Suivi de la precision des previsions par horizon</div>
          </div>
          <button
            onClick={load}
            className="cursor-pointer rounded-md border border-border bg-bg-control px-3 py-1.5 text-[10px] text-text-secondary"
          >
            Actualiser
          </button>
        </div>
      </div>

      <AppNav />

      <main className="flex-1 px-6 py-4">
        <div className="mx-auto max-w-[960px]">

          <div className="mb-4 flex flex-wrap gap-2.5">
            <select
              value={zoneFilter}
              onChange={e => setZoneFilter(e.target.value)}
              className="rounded-md border border-border bg-bg-inner px-2.5 py-1.5 text-[11px] text-text-primary"
            >
              <option value="">Toutes les zones</option>
              {ZONES.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}
            </select>
            <select
              value={horizonFilter}
              onChange={e => setHorizonFilter(e.target.value)}
              className="rounded-md border border-border bg-bg-inner px-2.5 py-1.5 text-[11px] text-text-primary"
            >
              <option value="">Tous les horizons</option>
              {HORIZONS.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              {[1,2,3].map(i => <div key={i} className="skeleton rounded-lg" style={{ height: 60 }} />)}
            </div>
          ) : error ? (
            <div className="rounded-lg border border-[#ef444433] bg-[#ef444411] p-4 text-center text-xs text-[#ef4444]">
              {error}
            </div>
          ) : data && data.total_evaluated === 0 ? (
            <div className="rounded-xl border border-border bg-bg-card p-8 text-center">
              <div className="mb-1.5 text-[13px] text-text-secondary">Aucune evaluation disponible</div>
              <div className="text-[11px] text-text-muted">
                Les forecasts sont enregistres a chaque appel et evalues quand l&apos;heure cible arrive.
                Premiere evaluation possible : +30min apres le premier forecast enregistre.
              </div>
            </div>
          ) : data && (
            <>
              <div className="mb-4 flex flex-wrap gap-3">
                <StatBox label="Evaluations" value={data.total_evaluated} />
                <StatBox label="MAE global" value={data.mae_global !== null ? `${data.mae_global} pts` : "-"} color={maeColor(data.mae_global)} />
                <StatBox label="Incidents surprises" value={data.incident_surprises} color={data.incident_surprises > 0 ? "#f97316" : "var(--text-secondary)"} />
              </div>

              <div className="mb-4 overflow-hidden rounded-xl border border-border bg-bg-card">
                <div className="border-b border-border px-4 py-3 text-[10px] font-semibold tracking-widest text-text-muted">
                  PRECISION PAR HORIZON
                </div>
                <table className="w-full border-collapse text-[11px]">
                  <thead>
                    <tr className="border-b border-border">
                      {["Horizon", "Evaluations", "MAE", "MAE (clean)", "Biais", "Min", "Max", "Surprises"].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-[10px] font-medium text-text-muted">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_horizon.map((h: ForecastAccuracyHorizon) => (
                      <tr key={h.horizon} className="border-b border-border">
                        <td className="px-3 py-2 font-semibold">{h.horizon}</td>
                        <td className="px-3 py-2">{h.n}</td>
                        <td className="px-3 py-2 font-semibold" style={{ color: maeColor(h.mae) }}>{h.mae ?? "-"}</td>
                        <td className="px-3 py-2" style={{ color: maeColor(h.mae_clean) }}>{h.mae_clean ?? "-"}</td>
                        <td className="px-3 py-2 text-[10px]">{biasLabel(h.bias)}</td>
                        <td className="px-3 py-2">{h.min_delta ?? "-"}</td>
                        <td className="px-3 py-2">{h.max_delta ?? "-"}</td>
                        <td className="px-3 py-2" style={{ color: h.n_surprise > 0 ? "#f97316" : "var(--text-muted)" }}>{h.n_surprise}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="overflow-hidden rounded-xl border border-border bg-bg-card">
                <div className="border-b border-border px-4 py-3 text-[10px] font-semibold tracking-widest text-text-muted">
                  DERNIERES EVALUATIONS
                </div>
                <div className="max-h-[400px] overflow-y-auto">
                  <table className="w-full border-collapse text-[11px]">
                    <thead>
                      <tr className="sticky top-0 border-b border-border bg-bg-card">
                        {["Zone", "Horizon", "Prevu", "Reel", "Delta", "Surprise", "Evalue a"].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-[10px] font-medium text-text-muted">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((ev: ForecastEvaluation, i: number) => (
                        <tr key={i} className="border-b border-border">
                          <td className="px-3 py-2 font-medium">{ev.zone_id}</td>
                          <td className="px-3 py-2">{ev.horizon}</td>
                          <td className="px-3 py-2">{ev.predicted_score}</td>
                          <td className="px-3 py-2">{ev.actual_score}</td>
                          <td
                            className="px-3 py-2 font-semibold"
                            style={{ color: Math.abs(ev.delta) <= 5 ? "#22c55e" : Math.abs(ev.delta) <= 10 ? "#f97316" : "#ef4444" }}
                          >
                            {ev.delta > 0 ? "+" : ""}{ev.delta}
                          </td>
                          <td className="px-3 py-2">
                            {ev.incident_surprise ? (
                              <span className="rounded bg-[#f9731622] px-1.5 py-0.5 text-[9px] text-[#f97316]">incident</span>
                            ) : "-"}
                          </td>
                          <td className="px-3 py-2 text-[10px] text-text-muted">
                            {ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleString("fr-FR", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.recent.length === 0 && (
                    <div className="p-4 text-center text-[11px] text-text-muted">Aucune evaluation recente</div>
                  )}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-4 text-[10px] text-text-muted">
                <span><span className="text-[#22c55e]">MAE &le; 5</span> = excellent</span>
                <span><span className="text-[#f97316]">MAE 5-10</span> = acceptable</span>
                <span><span className="text-[#ef4444]">MAE &gt; 10</span> = a ameliorer</span>
                <span>MAE clean = hors incidents surprises</span>
                <span>Biais &gt; 0 = sur-estimation</span>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="min-w-[120px] flex-1 rounded-[10px] border border-border bg-bg-card px-3.5 py-3">
      <div className="mb-1 text-[10px] text-text-muted">{label}</div>
      <div className="text-xl font-bold" style={{ color: color ?? "var(--text-primary)" }}>{value}</div>
    </div>
  );
}
