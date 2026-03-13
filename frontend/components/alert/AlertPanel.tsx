"use client";

import { useEffect, useState } from "react";
import { fetchAlerts } from "@/lib/api";
import type { Alert } from "@/domain/types";
import { REFRESH_INTERVAL } from "@/domain/constants";

const ALERT_META = {
  CRITIQUE: { emoji: "🔴", color: "#ef4444", label: "CRITIQUE" },
  TENDU:    { emoji: "🟠", color: "#f97316", label: "TENDU"    },
  CALME:    { emoji: "🟢", color: "#22c55e", label: "RETOUR CALME" },
};

function timeAgo(ts: string): string {
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60)  return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}min`;
  return `${Math.floor(diff / 3600)}h`;
}

export default function AlertPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [open,   setOpen]   = useState(true);
  const [error,  setError]  = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      const data = await fetchAlerts(10);
      setAlerts(data?.alerts ?? []);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError("Alertes indisponibles");
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, []);

  const unread = alerts.filter(a => a.alert_type !== "CALME").length;

  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls="alert-list"
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", cursor: "pointer", userSelect: "none", width: "100%", background: "transparent", border: "none", color: "inherit", font: "inherit" }}
      >
        <span style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.1em", flex: 1, textAlign: "left" }}>
          ALERTES
        </span>
        {unread > 0 && (
          <span style={{ fontSize: 9, background: "#ef444422", color: "#ef4444", border: "1px solid #ef444433", borderRadius: 10, padding: "1px 7px", fontWeight: 700 }}>
            {unread}
          </span>
        )}
        <span style={{ fontSize: 10, color: "var(--text-faint)" }} aria-hidden="true">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div id="alert-list" role="region" aria-label="Liste des alertes" style={{ borderTop: "1px solid var(--border)" }}>
          {error ? (
            <div style={{ padding: "14px", fontSize: 11, color: "var(--text-secondary)", textAlign: "center" }}>
              {error}
              <button onClick={load} style={{ display: "block", margin: "6px auto 0", fontSize: 10, color: "var(--accent-text)", background: "transparent", border: "none", cursor: "pointer" }}>
                Réessayer
              </button>
            </div>
          ) : alerts.length === 0 ? (
            <div style={{ padding: "14px", fontSize: 11, color: "var(--text-secondary)", textAlign: "center" }}>
              Aucune alerte enregistrée.
            </div>
          ) : (
            alerts.map((a, i) => {
              const meta = ALERT_META[a.alert_type] ?? ALERT_META.TENDU;
              const dir  = a.urban_score > a.prev_score ? "↑" : "↓";
              return (
                <div
                  key={`${a.ts}-${a.zone_id}`}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 14px",
                    borderBottom: i < alerts.length - 1 ? "1px solid var(--bg-control)" : undefined,
                    background: i === 0 ? `${meta.color}08` : undefined,
                  }}
                >
                  <span style={{ fontSize: 13 }}>{meta.emoji}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "var(--text-primary)", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {a.zone_name}
                    </div>
                    <div style={{ fontSize: 9, color: "var(--text-faint)", marginTop: 1 }}>
                      {meta.label} · {a.prev_score} {dir} {a.urban_score}
                    </div>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>
                    {timeAgo(a.ts)}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
