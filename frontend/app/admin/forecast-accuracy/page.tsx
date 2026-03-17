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
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", fontFamily: "monospace" }}>
      <div style={{ background: "var(--bg-card)", borderBottom: "1px solid var(--border)", padding: "14px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>Forecast Accuracy</div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>Suivi de la precision des previsions par horizon</div>
          </div>
          <button
            onClick={load}
            style={{ fontSize: 10, padding: "6px 12px", background: "var(--bg-control)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-secondary)", cursor: "pointer" }}
          >
            Actualiser
          </button>
        </div>
      </div>

      <AppNav />

      <main style={{ flex: 1, padding: "16px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>

          {/* Filters */}
          <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
            <select
              value={zoneFilter}
              onChange={e => setZoneFilter(e.target.value)}
              style={{ fontSize: 11, padding: "6px 10px", background: "var(--bg-inner)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-primary)" }}
            >
              <option value="">Toutes les zones</option>
              {ZONES.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}
            </select>
            <select
              value={horizonFilter}
              onChange={e => setHorizonFilter(e.target.value)}
              style={{ fontSize: 11, padding: "6px 10px", background: "var(--bg-inner)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text-primary)" }}
            >
              <option value="">Tous les horizons</option>
              {HORIZONS.map(h => <option key={h} value={h}>{h}</option>)}
            </select>
          </div>

          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 60, borderRadius: 8 }} />)}
            </div>
          ) : error ? (
            <div style={{ background: "#ef444411", border: "1px solid #ef444433", borderRadius: 8, padding: 16, fontSize: 12, color: "#ef4444", textAlign: "center" }}>
              {error}
            </div>
          ) : data && data.total_evaluated === 0 ? (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, padding: 32, textAlign: "center" }}>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 6 }}>Aucune evaluation disponible</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                Les forecasts sont enregistres a chaque appel et evalues quand l&apos;heure cible arrive.
                Premiere evaluation possible : +30min apres le premier forecast enregistre.
              </div>
            </div>
          ) : data && (
            <>
              {/* Global stats */}
              <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
                <StatBox label="Evaluations" value={data.total_evaluated} />
                <StatBox label="MAE global" value={data.mae_global !== null ? `${data.mae_global} pts` : "-"} color={maeColor(data.mae_global)} />
                <StatBox label="Incidents surprises" value={data.incident_surprises} color={data.incident_surprises > 0 ? "#f97316" : "var(--text-secondary)"} />
              </div>

              {/* Per-horizon table */}
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", marginBottom: 16 }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", fontWeight: 600, padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                  PRECISION PAR HORIZON
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Horizon", "Evaluations", "MAE", "MAE (clean)", "Biais", "Min", "Max", "Surprises"].map(h => (
                        <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--text-muted)", fontWeight: 500, fontSize: 10 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_horizon.map((h: ForecastAccuracyHorizon) => (
                      <tr key={h.horizon} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "8px 12px", fontWeight: 600 }}>{h.horizon}</td>
                        <td style={{ padding: "8px 12px" }}>{h.n}</td>
                        <td style={{ padding: "8px 12px", color: maeColor(h.mae), fontWeight: 600 }}>{h.mae ?? "-"}</td>
                        <td style={{ padding: "8px 12px", color: maeColor(h.mae_clean) }}>{h.mae_clean ?? "-"}</td>
                        <td style={{ padding: "8px 12px", fontSize: 10 }}>{biasLabel(h.bias)}</td>
                        <td style={{ padding: "8px 12px" }}>{h.min_delta ?? "-"}</td>
                        <td style={{ padding: "8px 12px" }}>{h.max_delta ?? "-"}</td>
                        <td style={{ padding: "8px 12px", color: h.n_surprise > 0 ? "#f97316" : "var(--text-muted)" }}>{h.n_surprise}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Recent evaluations */}
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
                <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", fontWeight: 600, padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                  DERNIERES EVALUATIONS
                </div>
                <div style={{ maxHeight: 400, overflowY: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)", position: "sticky", top: 0, background: "var(--bg-card)" }}>
                        {["Zone", "Horizon", "Prevu", "Reel", "Delta", "Surprise", "Evalue a"].map(h => (
                          <th key={h} style={{ padding: "8px 12px", textAlign: "left", color: "var(--text-muted)", fontWeight: 500, fontSize: 10 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((ev: ForecastEvaluation, i: number) => (
                        <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td style={{ padding: "8px 12px", fontWeight: 500 }}>{ev.zone_id}</td>
                          <td style={{ padding: "8px 12px" }}>{ev.horizon}</td>
                          <td style={{ padding: "8px 12px" }}>{ev.predicted_score}</td>
                          <td style={{ padding: "8px 12px" }}>{ev.actual_score}</td>
                          <td style={{
                            padding: "8px 12px",
                            fontWeight: 600,
                            color: Math.abs(ev.delta) <= 5 ? "#22c55e" : Math.abs(ev.delta) <= 10 ? "#f97316" : "#ef4444",
                          }}>
                            {ev.delta > 0 ? "+" : ""}{ev.delta}
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            {ev.incident_surprise ? (
                              <span style={{ fontSize: 9, padding: "2px 6px", background: "#f9731622", color: "#f97316", borderRadius: 4 }}>incident</span>
                            ) : "-"}
                          </td>
                          <td style={{ padding: "8px 12px", fontSize: 10, color: "var(--text-muted)" }}>
                            {ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleString("fr-FR", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {data.recent.length === 0 && (
                    <div style={{ padding: 16, textAlign: "center", fontSize: 11, color: "var(--text-muted)" }}>Aucune evaluation recente</div>
                  )}
                </div>
              </div>

              {/* Legend */}
              <div style={{ marginTop: 12, fontSize: 10, color: "var(--text-muted)", display: "flex", gap: 16, flexWrap: "wrap" }}>
                <span><span style={{ color: "#22c55e" }}>MAE &le; 5</span> = excellent</span>
                <span><span style={{ color: "#f97316" }}>MAE 5-10</span> = acceptable</span>
                <span><span style={{ color: "#ef4444" }}>MAE &gt; 10</span> = a ameliorer</span>
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
    <div style={{ flex: 1, minWidth: 120, background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 10, padding: "12px 14px" }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "var(--text-primary)" }}>{value}</div>
    </div>
  );
}
