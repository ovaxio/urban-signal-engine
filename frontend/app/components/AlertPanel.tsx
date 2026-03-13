"use client";

import { useEffect, useState } from "react";
import { fetchAlerts, scoreColor } from "@/lib/api";

type Alert = {
  ts: string;
  zone_id: string;
  zone_name: string;
  alert_type: "CRITIQUE" | "TENDU" | "CALME";
  urban_score: number;
  prev_score: number;
  level: string;
};

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

  const load = async () => {
    try {
      const data = await fetchAlerts(10);
      setAlerts(data?.alerts ?? []);
    } catch (_) {}
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  const unread = alerts.filter(a => a.alert_type !== "CALME").length;

  return (
    <div style={{ background: "#1a1d27", border: "1px solid #2d3148", borderRadius: 10, overflow: "hidden" }}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", cursor: "pointer", userSelect: "none" }}
      >
        <span style={{ fontSize: 10, color: "#64748b", fontWeight: 600, letterSpacing: "0.1em", flex: 1 }}>
          ALERTES
        </span>
        {unread > 0 && (
          <span style={{ fontSize: 9, background: "#ef444422", color: "#ef4444", border: "1px solid #ef444433", borderRadius: 10, padding: "1px 7px", fontWeight: 700 }}>
            {unread}
          </span>
        )}
        <span style={{ fontSize: 10, color: "#475569" }}>{open ? "▲" : "▼"}</span>
      </div>

      {/* Liste */}
      {open && (
        <div style={{ borderTop: "1px solid #2d3148" }}>
          {alerts.length === 0 ? (
            <div style={{ padding: "14px", fontSize: 11, color: "#334155", textAlign: "center" }}>
              Aucune alerte enregistrée.
            </div>
          ) : (
            alerts.map((a, i) => {
              const meta = ALERT_META[a.alert_type] ?? ALERT_META.TENDU;
              const dir  = a.urban_score > a.prev_score ? "↑" : "↓";
              return (
                <div
                  key={i}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 14px",
                    borderBottom: i < alerts.length - 1 ? "1px solid #1e2235" : undefined,
                    background: i === 0 ? `${meta.color}08` : undefined,
                  }}
                >
                  <span style={{ fontSize: 13 }}>{meta.emoji}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 11, color: "#e2e8f0", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {a.zone_name}
                    </div>
                    <div style={{ fontSize: 9, color: "#475569", marginTop: 1 }}>
                      {meta.label} · {a.prev_score} {dir} {a.urban_score}
                    </div>
                  </div>
                  <div style={{ fontSize: 10, color: "#334155", flexShrink: 0 }}>
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
