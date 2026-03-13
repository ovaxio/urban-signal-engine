"use client";

import type { HealthStatus } from "@/domain/types";
import styles from "./DashboardHeader.module.css";
import ThemeToggle from "@/components/theme/ThemeToggle";

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
    <header className={styles.header}>
      <div className={styles.inner}>

        {/* Row 1: Logo + Health (always visible) */}
        <div className={styles.topRow}>
          <div className={styles.brand}>
            <div
              className={styles.statusDot}
              style={{ background: simMode ? "#f97316" : "#22c55e", boxShadow: `0 0 8px ${simMode ? "#f97316" : "#22c55e"}` }}
            />
            <span className={styles.title}>URBAN SIGNAL ENGINE</span>
            <span className={styles.titleShort}>USE</span>
            {simMode
              ? <span className={styles.badgeSim}>SIMULATION · {simDate}</span>
              : <span className={styles.badgeLive}>LYON · LIVE</span>
            }
          </div>

          {/* Health — compact, always top-right */}
          <div className={styles.health}>
            {!simMode && health && (
              <>
                <span className={styles.healthText}>{dot} {age}s</span>
                <button
                  onClick={onRefresh}
                  aria-label="Rafraîchir les données"
                  className={styles.refreshBtn}
                >↻</button>
              </>
            )}
            <ThemeToggle />
          </div>
        </div>

        {/* Row 2: Simulation controls */}
        <div className={styles.controls}>
          <label htmlFor="sim-date" className={styles.srOnly}>Date de simulation</label>
          <input
            id="sim-date"
            type="date"
            value={simDate}
            onChange={e => onSimDateChange(e.target.value)}
            className={styles.dateInput}
          />
          <button
            onClick={onRunSim}
            disabled={!simDate || simLoading}
            className={styles.simBtn}
            style={{ opacity: (!simDate || simLoading) ? 0.5 : 1 }}
          >
            {simLoading ? "…" : "▶ Simuler"}
          </button>
          {simMode && (
            <button onClick={onExitSim} className={styles.liveBtn}>
              ⬤ Live
            </button>
          )}
        </div>
      </div>

      {/* Active events banner (simulation) */}
      {simMode && simEvents.length > 0 && (
        <div className={styles.eventsBanner}>
          <span className={styles.eventsLabel}>Événements actifs :</span>
          {simEvents.map(e => (
            <span key={e} className={styles.eventTag}>{e}</span>
          ))}
        </div>
      )}
    </header>
  );
}
