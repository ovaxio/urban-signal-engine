"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { fetchScores, fetchHealth, fetchSimulation, scoreColor } from "@/lib/api";
import "@/app/components/zone-map.css";
import AlertPanel from "@/app/components/AlertPanel";

const ZoneMap = dynamic<{ zones: any[] }>(
  () => import("@/app/components/ZoneMap"),
  { ssr: false, loading: () => <div style={{ height: 420, background: "#13161f", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", color: "#475569", fontSize: 12 }}>Chargement de la carte…</div> }
);

const REFRESH_INTERVAL = 30_000;

type FilterLevel = "all" | "TENDU" | "CRITIQUE";

export default function Home() {
  const [zones,       setZones]       = useState<any[]>([]);
  const [health,      setHealth]      = useState<any>(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);
  const [lastFetch,   setLastFetch]   = useState<Date | null>(null);
  const [filter,      setFilter]      = useState<FilterLevel>("all");
  const [simDate,     setSimDate]     = useState("");
  const [simMode,     setSimMode]     = useState(false);
  const [simEvents,   setSimEvents]   = useState<string[]>([]);
  const [simLoading,  setSimLoading]  = useState(false);

  // ── Chargement live ──────────────────────────────────────────
  const loadLive = useCallback(async () => {
    try {
      setError(null);
      const [data, h] = await Promise.all([fetchScores(), fetchHealth()]);
      setZones([...(data?.zones ?? [])].sort((a, b) => b.urban_score - a.urban_score));
      setHealth(h);
      setLastFetch(new Date());
    } catch (e) {
      setError("Impossible de contacter le backend");
    }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (simMode) return;
    loadLive();
    const id = setInterval(loadLive, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [loadLive, simMode]);

  // ── Mode simulation ──────────────────────────────────────────
  const runSimulation = useCallback(async () => {
    if (!simDate) return;
    setSimLoading(true);
    try {
      const data = await fetchSimulation(simDate);
      setZones([...(data?.zones ?? [])].sort((a, b) => b.urban_score - a.urban_score));
      setSimEvents(data?.active_events ?? []);
      setSimMode(true);
    } catch (e) {
      setError("Simulation échouée — vérifiez la date");
    }
    finally { setSimLoading(false); }
  }, [simDate]);

  const exitSim = useCallback(() => {
    setSimMode(false);
    setSimEvents([]);
    setError(null);
    loadLive();
  }, [loadLive]);

  // ── Stats globales ───────────────────────────────────────────
  const alertCount = zones.filter(z => z.urban_score >= 55).length;
  const avgScore   = zones.length ? Math.round(zones.reduce((s, z) => s + z.urban_score, 0) / zones.length) : 0;
  const topZone    = zones[0];

  // ── Filtrage ─────────────────────────────────────────────────
  const displayed = zones.filter(z => {
    if (filter === "TENDU")   return z.urban_score >= 55;
    if (filter === "CRITIQUE") return z.urban_score >= 72;
    return true;
  });

  const age = health?.cache_age ?? 0;
  const dot = age > 60 ? "🔴" : age > 30 ? "🟡" : "🟢";

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", fontFamily: "monospace" }}>

      {/* ── HEADER ── */}
      <header style={{ background: "#1a1d27", borderBottom: "1px solid #2d3148", padding: "12px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>

          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: simMode ? "#f97316" : "#22c55e", boxShadow: `0 0 8px ${simMode ? "#f97316" : "#22c55e"}`, flexShrink: 0 }} />
            <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "0.06em", whiteSpace: "nowrap" }}>URBAN SIGNAL ENGINE</span>
            {simMode
              ? <span style={{ fontSize: 11, color: "#f97316", background: "#f9731611", padding: "2px 8px", borderRadius: 4, border: "1px solid #f9731644", whiteSpace: "nowrap" }}>SIMULATION · {simDate}</span>
              : <span style={{ fontSize: 11, color: "#64748b", background: "#1e2235", padding: "2px 8px", borderRadius: 4, whiteSpace: "nowrap" }}>LYON · LIVE</span>
            }
          </div>

          {/* Contrôles simulation */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label htmlFor="sim-date" className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}>Date de simulation</label>
            <input
              id="sim-date"
              type="date"
              value={simDate}
              onChange={e => setSimDate(e.target.value)}
              style={{ fontSize: 11, color: "#94a3b8", background: "#1e2235", border: "1px solid #2d3148", borderRadius: 4, padding: "3px 8px", cursor: "pointer", minHeight: 32 }}
            />
            <button
              onClick={runSimulation}
              disabled={!simDate || simLoading}
              style={{ fontSize: 11, color: "#f97316", background: "#f9731611", border: "1px solid #f9731644", borderRadius: 4, padding: "6px 12px", cursor: "pointer", opacity: (!simDate || simLoading) ? 0.5 : 1, minHeight: 32 }}
            >
              {simLoading ? "…" : "▶ Simuler"}
            </button>
            {simMode && (
              <button
                onClick={exitSim}
                style={{ fontSize: 11, color: "#22c55e", background: "#22c55e11", border: "1px solid #22c55e44", borderRadius: 4, padding: "6px 12px", cursor: "pointer", minHeight: 32 }}
              >
                ⬤ Live
              </button>
            )}
          </div>

          {/* Health */}
          {!simMode && health && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: "#64748b" }}>{dot} cache {age}s</span>
              <button
                onClick={loadLive}
                aria-label="Rafraîchir les données"
                style={{ fontSize: 12, color: "#94a3b8", background: "#1e2235", border: "1px solid #2d3148", borderRadius: 4, padding: "4px 10px", cursor: "pointer", minHeight: 32, minWidth: 32 }}
              >↻</button>
            </div>
          )}
        </div>

        {/* Bannière événements actifs en simulation */}
        {simMode && simEvents.length > 0 && (
          <div style={{ maxWidth: 960, margin: "8px auto 0", fontSize: 11, color: "#f97316", display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span style={{ color: "#64748b" }}>Événements actifs :</span>
            {simEvents.map((e, i) => (
              <span key={e} style={{ background: "#f9731611", border: "1px solid #f9731633", borderRadius: 4, padding: "1px 8px" }}>{e}</span>
            ))}
          </div>
        )}
      </header>

      <main style={{ flex: 1, padding: "16px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {loading ? (
            <div style={{ textAlign: "center", color: "#94a3b8", marginTop: 80, fontSize: 14 }}>Chargement…</div>
          ) : error && zones.length === 0 ? (
            <div style={{ textAlign: "center", marginTop: 80 }}>
              <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 12 }}>{error}</div>
              <button
                onClick={loadLive}
                style={{ fontSize: 12, color: "#a5b4fc", background: "transparent", border: "1px solid #6366f144", borderRadius: 6, padding: "8px 20px", cursor: "pointer" }}
              >
                Réessayer
              </button>
            </div>
          ) : (
            <>
              {/* Error banner (non-blocking) */}
              {error && zones.length > 0 && (
                <div style={{ background: "#f9731611", border: "1px solid #f9731633", borderRadius: 8, padding: "8px 14px", marginBottom: 12, fontSize: 11, color: "#f97316", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{error}</span>
                  <button onClick={loadLive} style={{ fontSize: 10, color: "#a5b4fc", background: "transparent", border: "none", cursor: "pointer" }}>Réessayer</button>
                </div>
              )}

              {/* ── STATS BAR ── */}
              <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
                <StatCard label="zones analysées"   value={zones.length}  />
                <StatCard label="en alerte (≥55)"   value={alertCount}    color={alertCount > 0 ? "#f97316" : "#22c55e"} />
                <StatCard label="score moyen"        value={avgScore}      color={scoreColor(avgScore)} />
                {topZone && (
                  <StatCard label="zone la plus tendue" value={`${topZone.zone_name} · ${topZone.urban_score}`} color={scoreColor(topZone.urban_score)} />
                )}
              </div>

              {/* ── FILTRES ── */}
              <div role="group" aria-label="Filtrer par niveau" style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                {(["all", "TENDU", "CRITIQUE"] as FilterLevel[]).map(f => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    aria-pressed={filter === f}
                    style={{
                      fontSize: 11, fontWeight: 600, padding: "8px 16px", borderRadius: 6, cursor: "pointer", minHeight: 36,
                      border: filter === f ? "1px solid #6366f1" : "1px solid #2d3148",
                      background: filter === f ? "#6366f122" : "#1e2235",
                      color: filter === f ? "#a5b4fc" : "#94a3b8",
                    }}
                  >
                    {f === "all" ? "TOUTES" : f === "TENDU" ? "TENDU+" : "CRITIQUE"}
                    {f === "TENDU"    && ` (${zones.filter(z => z.urban_score >= 55).length})`}
                    {f === "CRITIQUE" && ` (${zones.filter(z => z.urban_score >= 72).length})`}
                  </button>
                ))}
              </div>

              {/* ── CARTE ── */}
              <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid #2d3148", marginBottom: 16 }} role="img" aria-label="Carte des zones urbaines de Lyon">
                <ZoneMap zones={displayed} />
              </div>

              {/* ── ALERTES + GRILLE ── */}
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) clamp(200px, 25%, 260px)", gap: 16, alignItems: "start" }}>

              {/* Grille zones */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10, minWidth: 0 }}>
                {displayed.length === 0 ? (
                  <div style={{ gridColumn: "1 / -1", textAlign: "center", padding: 32, color: "#94a3b8", fontSize: 12 }}>
                    Aucune zone ne correspond au filtre sélectionné.
                  </div>
                ) : displayed.map((z: any) => {
                  const isAlert = z.urban_score >= 55;
                  const col = scoreColor(z.urban_score);
                  const barW = `${z.urban_score}%`;
                  return (
                    <Link key={z.zone_id} href={`/zones/${z.zone_id}${simMode ? `?sim=${simDate}` : ""}`}>
                      <div style={{
                        background: isAlert ? `${col}0d` : "#1a1d27",
                        border: `1px solid ${col}${isAlert ? "66" : "33"}`,
                        borderRadius: 10,
                        padding: "14px 16px",
                        cursor: "pointer",
                        boxShadow: isAlert ? `0 0 14px ${col}22` : "none",
                        transition: "box-shadow 0.3s",
                        position: "relative",
                        minWidth: 0,
                      }}>
                        {/* Barre score */}
                        <div style={{ height: 3, background: "#1e2235", borderRadius: 2, marginBottom: 10 }}>
                          <div style={{ height: "100%", width: barW, background: col, borderRadius: 2, transition: "width 0.5s" }} />
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>{z.zone_name}</div>
                          {isAlert && <div style={{ width: 6, height: 6, borderRadius: "50%", background: col, boxShadow: `0 0 5px ${col}`, flexShrink: 0 }} />}
                        </div>

                        <div style={{ fontSize: 32, fontWeight: 800, color: col, lineHeight: 1 }}>{z.urban_score}</div>
                        <div style={{ fontSize: 10, color: col, marginTop: 3, fontWeight: 700, letterSpacing: "0.05em" }}>{z.level}</div>

                        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 2 }}>
                          {(z.top_causes ?? []).length > 0
                            ? (z.top_causes as string[]).slice(0, 2).map((c: string, i: number) => (
                                <div key={i} style={{ fontSize: 9, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>▸ {c}</div>
                              ))
                            : <div style={{ fontSize: 9, color: "#94a3b8", fontStyle: "italic" }}>Conditions normales</div>
                          }
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>

              {/* Panel alertes */}
              {!simMode && <AlertPanel />}

              </div>{/* fin grille alertes+zones */}

              {/* Info dernière MàJ */}
              {lastFetch && !simMode && (
                <p style={{ marginTop: 12, fontSize: 10, color: "#64748b", textAlign: "right" }}>
                  Dernière mise à jour : {lastFetch.toLocaleTimeString("fr-FR")}
                </p>
              )}
            </>
          )}
        </div>
      </main>

      <footer style={{ background: "#13161f", borderTop: "1px solid #1e2235", padding: "8px 24px", fontSize: 10, color: "#64748b", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
        <span>Urban Signal Engine · données ouvertes · Lyon</span>
        <span>UrbanScore = Φ·(wT·T + wM·M + wE·E + wP·P) + λ₂·A + λ₃·C + λ₄·S</span>
      </footer>
    </div>
  );
}

// ── Composant stat ──────────────────────────────────────────────────────────

function StatCard({ label, value, color = "#64748b" }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ background: "#1a1d27", border: "1px solid #2d3148", borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9, color: "#94a3b8", letterSpacing: "0.08em", marginBottom: 4 }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
    </div>
  );
}
