"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { fetchScores, fetchHealth, fetchSimulation, fetchAlerts } from "@/lib/api";
import { scoreColor } from "@/domain/scoring";
import { REFRESH_INTERVAL } from "@/domain/constants";
import type { ZoneSummary, HealthStatus, FilterLevel, Alert } from "@/domain/types";

import DashboardHeader from "@/components/layout/DashboardHeader";
import AppNav          from "@/components/layout/AppNav";
import FilterBar       from "@/components/layout/FilterBar";
import StatCard        from "@/components/ui/StatCard";
import ErrorState      from "@/components/ui/ErrorState";
import ZoneGrid        from "@/components/zone/ZoneGrid";
import AlertPanel      from "@/components/alert/AlertPanel";

const ZoneMap = dynamic<{ zones: ZoneSummary[] }>(
  () => import("@/components/map/ZoneMap"),
  { ssr: false, loading: () => <div className="flex h-[420px] items-center justify-center rounded-xl bg-bg-inner text-xs text-text-faint">Chargement de la carte…</div> }
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
  const [alerts,      setAlerts]      = useState<Alert[]>([]);

  // ── Live data (auto-retry on cold start) ──────────────────────
  const [loadMsg, setLoadMsg] = useState("Connexion au backend…");
  const retryRef = useRef(0);

  const loadLive = useCallback(async () => {
    try {
      setError(null);
      const [data, h, alertData] = await Promise.all([
        fetchScores(), fetchHealth(), fetchAlerts(10),
      ]);
      setZones([...(data?.zones ?? [])].sort((a: ZoneSummary, b: ZoneSummary) => b.urban_score - a.urban_score));
      setHealth(h);
      setAlerts(alertData?.alerts ?? []);
      setLastFetch(new Date());
      retryRef.current = 0;
      setLoading(false);
    } catch {
      if (loading && retryRef.current < 4) {
        retryRef.current += 1;
        const msgs = [
          "Connexion au backend…",
          "Réveil du serveur en cours…",
          "Le serveur démarre, encore quelques secondes…",
          "Presque prêt…",
        ];
        setLoadMsg(msgs[retryRef.current] ?? msgs[msgs.length - 1]);
        setTimeout(loadLive, 4000);
        return;
      }
      setError("Impossible de contacter le backend");
      setLoading(false);
    }
  }, [loading]);

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
    <div className="flex min-h-screen flex-col">

      <DashboardHeader
        simMode={simMode} simDate={simDate} simLoading={simLoading}
        simEvents={simEvents} health={health}
        onSimDateChange={setSimDate} onRunSim={runSimulation}
        onExitSim={exitSim} onRefresh={loadLive}
      />
      <AppNav />

      <main className="flex-1 px-6 py-4">
        <div className="mx-auto max-w-[960px]">
          {loading ? (
            <div className="flex flex-col gap-4">
              <div className="py-3 text-center text-xs tracking-wide text-text-muted">
                {loadMsg}
              </div>
              <div className="flex flex-wrap gap-3">
                {[1,2,3,4].map(i => <div key={i} className="skeleton min-w-[120px] flex-1" style={{ height: 52 }} />)}
              </div>
              <div className="skeleton rounded-xl" style={{ height: 420 }} />
              <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2.5">
                {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton rounded-[10px]" style={{ height: 140 }} />)}
              </div>
            </div>
          ) : error && zones.length === 0 ? (
            <ErrorState message={error} onRetry={loadLive} />
          ) : (
            <>
              {error && zones.length > 0 && (
                <div className="mb-3 flex items-center justify-between rounded-lg border border-[#f9731633] bg-[#f9731611] px-3.5 py-2 text-[11px] text-[#f97316]">
                  <span>{error}</span>
                  <button onClick={loadLive} className="cursor-pointer border-none bg-transparent text-[10px] text-accent-text">Réessayer</button>
                </div>
              )}

              <div className="mb-4 flex flex-wrap gap-3">
                <StatCard label="zones surveillées" value={zones.length} />
                <StatCard label="zones sous tension" value={alertCount} color={alertCount > 0 ? "#f97316" : "#22c55e"} />
                <StatCard label="score moyen" value={avgScore} color={scoreColor(avgScore)} />
                {topZone && <StatCard label="zone la plus tendue" value={`${topZone.zone_name} · ${topZone.urban_score}`} color={scoreColor(topZone.urban_score)} />}
              </div>

              <FilterBar filter={filter} zones={zones} onFilterChange={setFilter} />

              <div className="mb-4 overflow-hidden rounded-xl border border-border" role="img" aria-label="Carte des zones urbaines de Lyon">
                <ZoneMap zones={displayed} />
              </div>

              <div className="grid items-start gap-4" style={{ gridTemplateColumns: "minmax(0, 1fr) clamp(200px, 25%, 260px)" }}>
                <ZoneGrid zones={displayed} simDate={simMode ? simDate : undefined} />
                {!simMode && <AlertPanel alerts={alerts} />}
              </div>

              {lastFetch && !simMode && (
                <p className="mt-3 text-right text-[10px] text-text-muted">
                  Dernière mise à jour : {lastFetch.toLocaleTimeString("fr-FR")}
                </p>
              )}
            </>
          )}
        </div>
      </main>

      <footer className="flex flex-wrap gap-1 border-t border-bg-control bg-bg-inner px-6 py-2 text-[10px] text-text-muted" style={{ justifyContent: "space-between" }}>
        <span>Urban Signal Engine · données ouvertes · Lyon</span>
        <span>Score calculé en temps réel à partir de 5 sources de données urbaines</span>
      </footer>
    </div>
  );
}
