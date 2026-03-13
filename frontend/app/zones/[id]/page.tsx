import Link from "next/link";
import { fetchDetail, fetchForecast, fetchSimulationDetail, scoreColor } from "@/lib/api";
import ZoneHistoryChart from "@/app/components/ZoneHistoryChart";

type PageProps = {
  params:       { id: string };
  searchParams: { sim?: string };
};

export default async function ZonePage({ params, searchParams }: PageProps) {
  const simDate = searchParams.sim ?? null;
  const isSimMode = !!simDate;

  let detail: any   = null;
  let forecast: any = null;

  try {
    if (isSimMode) {
      detail = await fetchSimulationDetail(params.id, simDate!);
    } else {
      [detail, forecast] = await Promise.all([
        fetchDetail(params.id, { cache: "no-store" }),
        fetchForecast(params.id, { cache: "no-store" }),
      ]);
    }
  } catch (_) {}

  if (!detail) return (
    <div style={{ padding: 40, textAlign: "center" }}>
      <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 12 }}>Zone introuvable ou backend indisponible.</div>
      <Link href="/" style={{ color: "#a5b4fc", fontSize: 12 }}>← Retour au tableau de bord</Link>
    </div>
  );

  const z   = detail;
  const col = scoreColor(z.urban_score);
  const backHref = isSimMode ? `/?sim=${simDate}` : "/";

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* ── HEADER ── */}
      <header style={{ background: "#1a1d27", borderBottom: "1px solid #2d3148", padding: "12px 24px", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <Link href={backHref} style={{ color: "#64748b", fontSize: 12 }}>← Toutes les zones</Link>
        <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "0.06em" }}>URBAN SIGNAL ENGINE</span>
        {isSimMode ? (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", padding: "2px 10px", borderRadius: 4 }}>
            SIMULATION · {simDate}
          </span>
        ) : (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "#64748b" }}>
            Live · refresh serveur à chaque requête
          </span>
        )}
      </header>

      {/* ── BANNIÈRE ÉVÉNEMENTS (simulation) ── */}
      {isSimMode && z.sim_events?.length > 0 && (
        <div style={{ background: "#1a1d2799", borderBottom: "1px solid #f9731633", padding: "6px 24px", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#64748b" }}>ÉVÉNEMENTS ACTIFS :</span>
          {z.sim_events.map((e: string, i: number) => (
            <span key={i} style={{ fontSize: 10, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", borderRadius: 4, padding: "1px 8px" }}>{e}</span>
          ))}
        </div>
      )}

      <main style={{ maxWidth: 700, margin: "0 auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>

        {/* ── SCORE HEADER ── */}
        <div style={{ background: "#1a1d27", borderRadius: 12, padding: 24, border: `1px solid ${col}33`, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 26, fontWeight: 800 }}>{z.zone_name}</div>
            {!isSimMode && (
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                φ = {z.components.phi.toFixed(2)} · {new Date(z.timestamp).toLocaleTimeString("fr-FR", { timeZone: "Europe/Paris" })}
              </div>
            )}
            {isSimMode && (
              <div style={{ fontSize: 12, color: "#f97316", marginTop: 4 }}>
                Simulation · {simDate} · φ = {z.components.phi.toFixed(2)}
              </div>
            )}
            <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 12, lineHeight: 1.7 }}>{z.explanation}</div>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
            <div style={{ fontSize: 56, fontWeight: 900, color: col, lineHeight: 1 }}>{z.urban_score}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: col, marginTop: 4 }}>{z.level}</div>
          </div>
        </div>

        {/* ── SIGNAUX ── */}
        <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
          <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>SIGNAUX</div>
          {Object.entries(z.signals as Record<string, number>)
            .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
            .map(([key, val]) => {
              const v   = val as number;
              const pct = Math.min(100, Math.abs(v) / 3 * 100);
              const c   = scoreColor(Math.min(100, 30 + Math.abs(v) * 25));
              const weight = WEIGHTS[key] ?? 0;
              return (
                <div key={key} style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                    <span style={{ color: "#e2e8f0" }}>{SIGNAL_LABELS[key] ?? key}</span>
                    <span style={{ color: c, fontWeight: 600 }}>
                      {v >= 0 ? "+" : ""}{v.toFixed(2)}σ · {weight}%
                    </span>
                  </div>
                  <div style={{ height: 5, background: "#1e2235", borderRadius: 3 }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: c, borderRadius: 3 }} />
                  </div>
                </div>
              );
            })}
        </div>

        {/* ── PERTURBATIONS EN COURS ── */}
        {!isSimMode && z.incident_events?.length > 0 && (
          <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #ef444433" }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>PERTURBATIONS EN COURS</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {z.incident_events.map((ev: any, i: number) => (
                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", background: "#13161f", borderRadius: 8, borderLeft: `3px solid ${ev.ends_soon ? "#f97316" : "#ef4444"}` }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>{EVENT_ICONS[ev.type] ?? "⚠️"}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ev.label}</div>
                    {(ev.detail || ev.direction) && (
                      <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {ev.detail}{ev.detail && ev.direction ? " · " : ""}{ev.direction}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 6, marginTop: 3, flexWrap: "wrap", alignItems: "center" }}>
                      {ev.delay_min > 0 && (
                        <span style={{ fontSize: 9, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", padding: "1px 5px", borderRadius: 3 }}>+{ev.delay_min} min</span>
                      )}
                      {ev.end && (
                        <span style={{ fontSize: 10, color: ev.ends_soon ? "#f97316" : "#64748b" }}>
                          {ev.ends_soon ? `⏳ Fin prévue ${ev.end}` : `Jusqu'au ${ev.end}`}
                        </span>
                      )}
                    </div>
                  </div>
                  <span style={{ fontSize: 9, color: ev.weight >= 2.0 ? "#ef4444" : "#94a3b8", background: "#1e2235", padding: "2px 6px", borderRadius: 4, flexShrink: 0 }}>
                    {EVENT_TYPE_LABELS[ev.type] ?? ev.type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── COMPOSANTES ── */}
        <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
          <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>COMPOSANTES</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 8 }}>
            {(["risk","anomaly","conv","spread","phi"] as const).map(k => (
              <div key={k} style={{ textAlign: "center", padding: 12, background: "#13161f", borderRadius: 8 }}>
                <div style={{ fontSize: 9, color: "#64748b", marginBottom: 4, letterSpacing: "0.06em" }}>{k.toUpperCase()}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#a5b4fc" }}>{(z.components[k] as number).toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── PRÉVISION (live uniquement) ── */}
        {!isSimMode && forecast && (
          <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>PRÉVISION</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))", gap: 10 }}>
              <div style={{ textAlign: "center", padding: 14, background: "#13161f", borderRadius: 8, border: `1px solid ${scoreColor(forecast.current_score)}44` }}>
                <div style={{ fontSize: 10, color: "#64748b", marginBottom: 5 }}>Maintenant</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(forecast.current_score) }}>{forecast.current_score}</div>
                <div style={{ fontSize: 10, color: scoreColor(forecast.current_score), marginTop: 3 }}>{forecast.current_level}</div>
              </div>
              {forecast.forecast.map((f: any) => (
                <div key={f.horizon_min} style={{ textAlign: "center", padding: 14, background: "#13161f", borderRadius: 8, border: `1px solid ${scoreColor(f.urban_score)}33` }}>
                  <div style={{ fontSize: 10, color: "#64748b", marginBottom: 5 }}>+{f.horizon_min} min</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(f.urban_score) }}>{f.urban_score}</div>
                  <div style={{ fontSize: 10, color: scoreColor(f.urban_score), marginTop: 3 }}>{f.level}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 10, color: "#64748b", marginTop: 8 }}>{forecast.disclaimer}</div>
          </div>
        )}

        {/* ── ZONES VOISINES ── */}
        <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
          <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>ZONES VOISINES</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {z.neighbors.map((n: any) => (
              <Link key={n.zone_id} href={`/zones/${n.zone_id}${isSimMode ? `?sim=${simDate}` : ""}`}>
                <div style={{ padding: "10px 16px", background: "#13161f", borderRadius: 8, border: `1px solid ${scoreColor(n.urban_score)}44`, cursor: "pointer" }}>
                  <div style={{ fontSize: 11, color: "#94a3b8" }}>{n.zone_name}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: scoreColor(n.urban_score) }}>{n.urban_score}</div>
                  <div style={{ fontSize: 9, color: scoreColor(n.urban_score), marginTop: 2 }}>{n.level}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* ── HISTORIQUE (live uniquement) ── */}
        {!isSimMode && <ZoneHistoryChart zoneId={detail.zone_id} limit={48} />}

        {/* ── MESSAGE SIMULATION ── */}
        {isSimMode && (
          <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #f9731622", textAlign: "center" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>
              Simulation · l'historique et les prévisions ne sont pas disponibles en mode simulation.
            </div>
            <Link href={`/zones/${params.id}`} style={{ fontSize: 11, color: "#a5b4fc", marginTop: 8, display: "inline-block" }}>
              Voir les données live →
            </Link>
          </div>
        )}

      </main>
    </div>
  );
}

// ── Constantes ─────────────────────────────────────────────────────────────────

const SIGNAL_LABELS: Record<string, string> = {
  traffic:   "Trafic",
  weather:   "Météo",
  event:     "Événement",
  transport: "Transport TCL",
  incident:  "Incidents",
};

const WEIGHTS: Record<string, number> = {
  traffic:   30,
  weather:   10,
  event:      5,
  transport: 25,
  incident:  30,
};

const EVENT_ICONS: Record<string, string> = {
  roadClosed:       "🚧",
  march:            "✊",
  demonstration:    "✊",
  publicEvent:      "🎭",
  sportEvent:       "🏟️",
  other:            "⚠️",
  Activities:       "🎭",
  NetworkManagement:"🚧",
  AbnormalTraffic:  "🚦",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  roadClosed:       "Fermeture",
  march:            "Manifestation",
  demonstration:    "Manifestation",
  publicEvent:      "Événement",
  sportEvent:       "Sport",
  other:            "Divers",
  Activities:       "Activité",
  NetworkManagement:"Réseau",
  AbnormalTraffic:  "Trafic anormal",
};
