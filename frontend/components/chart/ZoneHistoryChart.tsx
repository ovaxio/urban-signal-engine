"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchHistory } from "@/lib/api";
import type { HistoryPoint } from "@/domain/types";

type Props = {
  zoneId: string;
  limit?: number;
};

const SERIES = [
  { key: "urban_score", label: "Score urbain", color: "#6366f1", axis: "score"   },
  { key: "traffic",     label: "Trafic",       color: "#f97316", axis: "signals" },
  { key: "weather",     label: "Météo",         color: "#38bdf8", axis: "signals" },
  { key: "transport",   label: "Transport",     color: "#a78bfa", axis: "signals" },
  { key: "event",       label: "Événement",     color: "#34d399", axis: "signals" },
] as const;

function formatTs(ts: string): string {
  return new Date(ts).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

export default function ZoneHistoryChart({ zoneId, limit = 48 }: Props) {
  const [data,    setData]    = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>(
    Object.fromEntries(SERIES.map(s => [s.key, true]))
  );

  useEffect(() => {
    setLoading(true);
    fetchHistory(zoneId, limit)
      .then(json => setData([...json.history].reverse()))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [zoneId, limit]);

  const toggle = (key: string) => setVisible(v => ({ ...v, [key]: !v[key] }));

  if (loading) return <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Chargement historique…</p>;
  if (error)   return <p style={{ fontSize: 13, color: "#ef4444" }}>Erreur : {error}</p>;
  if (!data.length) return <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>Pas encore d'historique.</p>;

  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Historique — {data.length} relevés</h2>
          <div style={{ marginTop: 4, display: "flex", gap: 16, fontSize: 11, color: "var(--text-muted)" }}>
            <span><span style={{ color: "#6366f1", fontWeight: 500 }}>Gauche</span> — Score (0–100)</span>
            <span><span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>Droite</span> — Signaux bruts</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {SERIES.map(s => (
            <button
              key={s.key}
              onClick={() => toggle(s.key)}
              style={{
                display: "flex", alignItems: "center", gap: 4, borderRadius: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer",
                background: visible[s.key] ? s.color + "22" : "transparent",
                color:      visible[s.key] ? s.color : "var(--text-muted)",
                border:     `1px solid ${visible[s.key] ? s.color : "var(--border)"}`,
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="ts"
            tickFormatter={formatTs}
            tick={{ fontSize: 11, fill: "#71717a" }}
            interval="preserveStartEnd"
          />
          <YAxis
            yAxisId="score"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: "#6366f1" }}
            tickFormatter={v => `${v}`}
            width={36}
          />
          <YAxis
            yAxisId="signals"
            orientation="right"
            tick={{ fontSize: 11, fill: "#71717a" }}
            tickFormatter={v => v.toFixed(1)}
            width={44}
          />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
            labelFormatter={(label) => formatTs(String(label))}
            formatter={(val: any, name: any) => {
              const serie = SERIES.find(s => s.key === name);
              const numValue = typeof val === 'number' ? val : parseFloat(val);
              return [!isNaN(numValue) ? numValue.toFixed(2) : "—", serie?.label ?? name];
            }}
          />
          <Legend
            formatter={name => SERIES.find(s => s.key === name)?.label ?? name}
            wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }}
          />
          {SERIES.map(s => (
            <Line
              key={s.key}
              yAxisId={s.axis}
              type="monotone"
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={s.key === "urban_score" ? 2.5 : 1.5}
              dot={false}
              hide={!visible[s.key]}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
