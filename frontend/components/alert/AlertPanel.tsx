"use client";

import { useState } from "react";
import type { Alert } from "@/domain/types";

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

type Props = {
  alerts: Alert[];
};

export default function AlertPanel({ alerts }: Props) {
  const [open, setOpen] = useState(true);

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
          {alerts.length === 0 ? (
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
