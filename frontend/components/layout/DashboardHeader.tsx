"use client";

import type { HealthStatus } from "@/domain/types";

type Props = {
  simMode: boolean;
  simDate: string;
  simLoading: boolean;
  simEvents: string[];
  health: HealthStatus | null;
  onSimDateChange: (date: string) => void;
  onRunSim: () => void;
  onExitSim: () => void;
  onRefresh: () => void;
};

export default function DashboardHeader({
  simMode, simDate, simLoading, simEvents, health,
  onSimDateChange, onRunSim, onExitSim, onRefresh,
}: Props) {
  const age = health?.cache_age ?? 0;
  const dot = age > 60 ? "🔴" : age > 30 ? "🟡" : "🟢";

  return (
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

        {/* Simulation controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label htmlFor="sim-date" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}>Date de simulation</label>
          <input
            id="sim-date"
            type="date"
            value={simDate}
            onChange={e => onSimDateChange(e.target.value)}
            style={{ fontSize: 11, color: "#94a3b8", background: "#1e2235", border: "1px solid #2d3148", borderRadius: 4, padding: "3px 8px", cursor: "pointer", minHeight: 32 }}
          />
          <button
            onClick={onRunSim}
            disabled={!simDate || simLoading}
            style={{ fontSize: 11, color: "#f97316", background: "#f9731611", border: "1px solid #f9731644", borderRadius: 4, padding: "6px 12px", cursor: "pointer", opacity: (!simDate || simLoading) ? 0.5 : 1, minHeight: 32 }}
          >
            {simLoading ? "…" : "▶ Simuler"}
          </button>
          {simMode && (
            <button
              onClick={onExitSim}
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
              onClick={onRefresh}
              aria-label="Rafraîchir les données"
              style={{ fontSize: 12, color: "#94a3b8", background: "#1e2235", border: "1px solid #2d3148", borderRadius: 4, padding: "4px 10px", cursor: "pointer", minHeight: 32, minWidth: 32 }}
            >↻</button>
          </div>
        )}
      </div>

      {/* Active events banner (simulation) */}
      {simMode && simEvents.length > 0 && (
        <div style={{ maxWidth: 960, margin: "8px auto 0", fontSize: 11, color: "#f97316", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span style={{ color: "#64748b" }}>Événements actifs :</span>
          {simEvents.map(e => (
            <span key={e} style={{ background: "#f9731611", border: "1px solid #f9731633", borderRadius: 4, padding: "1px 8px" }}>{e}</span>
          ))}
        </div>
      )}
    </header>
  );
}
