"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { fetchScores, fetchHealth, fetchSimulation } from "@/lib/api";
import { scoreColor } from "@/domain/scoring";
import { REFRESH_INTERVAL } from "@/domain/constants";
import type { ZoneSummary, HealthStatus, FilterLevel } from "@/domain/types";

import DashboardHeader from "@/components/layout/DashboardHeader";
import AppNav          from "@/components/layout/AppNav";
import FilterBar       from "@/components/layout/FilterBar";
import StatCard        from "@/components/ui/StatCard";
import ErrorState      from "@/components/ui/ErrorState";
import ZoneGrid        from "@/components/zone/ZoneGrid";
import AlertPanel      from "@/components/alert/AlertPanel";

const ZoneMap = dynamic<{ zones: ZoneSummary[] }>(
  () => import("@/components/map/ZoneMap"),
  { ssr: false, loading: () => <div style={{ height: 420, background: "var(--bg-inner)", borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-faint)", fontSize: 12 }}>Chargement de la carte…</div> }
);

export default function Home() {
  const [zones,       setZones]       = useState<ZoneSummary[]>([]);
  const [health,      setHealth]      = useState<HealthStatus | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);
  const [lastFetch,   setLastFetch]   = useState<Date | null>(null);
  const [filter,      setFilter]      = useState<FilterLevel>("all");
  const [simDate,     setSimDate]     = useState("");
  const [simMode,     setSimMode]     = useState(false);
  const [simEvents,   setSimEvents]   = useState<string[]>([]);
  const [simLoading,  setSimLoading]  = useState(false);

  // ── Live data ─────────────────────────────────────────────────
  const loadLive = useCallback(async () => {
    try {
      setError(null);
      const [data, h] = await Promise.all([fetchScores(), fetchHealth()]);
      setZones([...(data?.zones ?? [])].sort((a: ZoneSummary, b: ZoneSummary) => b.urban_score - a.urban_score));
      setHealth(h);
      setLastFetch(new Date());
    } catch {
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

  // ── Simulation ────────────────────────────────────────────────
  const runSimulation = useCallback(async () => {
    if (!simDate) return;
    setSimLoading(true);
    try {
      const data = await fetchSimulation(simDate);
      setZones([...(data?.zones ?? [])].sort((a: ZoneSummary, b: ZoneSummary) => b.urban_score - a.urban_score));
      setSimEvents(data?.active_events ?? []);
      setSimMode(true);
    } catch {
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

  // ── Derived state ─────────────────────────────────────────────
  const alertCount = zones.filter(z => z.urban_score >= 55).length;
  const avgScore   = zones.length ? Math.round(zones.reduce((s, z) => s + z.urban_score, 0) / zones.length) : 0;
  const topZone    = zones[0];

  const displayed = zones.filter(z => {
    if (filter === "TENDU")    return z.urban_score >= 55;
    if (filter === "CRITIQUE") return z.urban_score >= 72;
    return true;
  });

  // ── Render ────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", fontFamily: "monospace" }}>

      <DashboardHeader
        simMode={simMode} simDate={simDate} simLoading={simLoading}
        simEvents={simEvents} health={health}
        onSimDateChange={setSimDate} onRunSim={runSimulation}
        onExitSim={exitSim} onRefresh={loadLive}
      />
      <AppNav />

      <main style={{ flex: 1, padding: "16px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Skeleton stats */}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 52, flex: 1, minWidth: 120 }} />)}
              </div>
              {/* Skeleton map */}
              <div className="skeleton" style={{ height: 420, borderRadius: 12 }} />
              {/* Skeleton grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton" style={{ height: 140, borderRadius: 10 }} />)}
              </div>
            </div>
          ) : error && zones.length === 0 ? (
            <ErrorState message={error} onRetry={loadLive} />
          ) : (
            <>
              {/* Non-blocking error banner */}
              {error && zones.length > 0 && (
                <div style={{ background: "#f9731611", border: "1px solid #f9731633", borderRadius: 8, padding: "8px 14px", marginBottom: 12, fontSize: 11, color: "#f97316", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{error}</span>
                  <button onClick={loadLive} style={{ fontSize: 10, color: "var(--accent-text)", background: "transparent", border: "none", cursor: "pointer" }}>Réessayer</button>
                </div>
              )}

              {/* Stats */}
              <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
                <StatCard label="zones analysées" value={zones.length} />
                <StatCard label="en alerte (≥55)" value={alertCount} color={alertCount > 0 ? "#f97316" : "#22c55e"} />
                <StatCard label="score moyen" value={avgScore} color={scoreColor(avgScore)} />
                {topZone && <StatCard label="zone la plus tendue" value={`${topZone.zone_name} · ${topZone.urban_score}`} color={scoreColor(topZone.urban_score)} />}
              </div>

              <FilterBar filter={filter} zones={zones} onFilterChange={setFilter} />

              {/* Map */}
              <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)", marginBottom: 16 }} role="img" aria-label="Carte des zones urbaines de Lyon">
                <ZoneMap zones={displayed} />
              </div>

              {/* Grid + Alerts */}
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) clamp(200px, 25%, 260px)", gap: 16, alignItems: "start" }}>
                <ZoneGrid zones={displayed} simDate={simMode ? simDate : undefined} />
                {!simMode && <AlertPanel />}
              </div>

              {lastFetch && !simMode && (
                <p style={{ marginTop: 12, fontSize: 10, color: "var(--text-muted)", textAlign: "right" }}>
                  Dernière mise à jour : {lastFetch.toLocaleTimeString("fr-FR")}
                </p>
              )}
            </>
          )}
        </div>
      </main>

      <footer style={{ background: "var(--bg-inner)", borderTop: "1px solid var(--bg-control)", padding: "8px 24px", fontSize: 10, color: "var(--text-muted)", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
        <span>Urban Signal Engine · données ouvertes · Lyon</span>
        <span>UrbanScore = Φ·(wT·T + wM·M + wE·E + wP·P) + λ₂·A + λ₃·C + λ₄·S</span>
      </footer>
    </div>
  );
}
