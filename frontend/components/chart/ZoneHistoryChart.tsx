"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
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
    fetch(`${process.env.NEXT_PUBLIC_API_BASE}/zones/${zoneId}/history?limit=${limit}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(json => setData([...json.history].reverse()))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [zoneId, limit]);

  const toggle = (key: string) => setVisible(v => ({ ...v, [key]: !v[key] }));

  if (loading) return <p className="text-sm text-zinc-400">Chargement historique…</p>;
  if (error)   return <p className="text-sm text-red-400">Erreur : {error}</p>;
  if (!data.length) return <p className="text-sm text-zinc-400">Pas encore d'historique.</p>;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">Historique — {data.length} relevés</h2>
          <div className="mt-1 flex gap-4 text-xs text-zinc-500">
            <span><span className="text-indigo-400 font-medium">Gauche</span> — Score (0–100)</span>
            <span><span className="text-zinc-400 font-medium">Droite</span> — Signaux bruts</span>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {SERIES.map(s => (
            <button
              key={s.key}
              onClick={() => toggle(s.key)}
              className="flex items-center gap-1 rounded px-2 py-0.5 text-xs transition"
              style={{
                background: visible[s.key] ? s.color + "22" : "transparent",
                color:      visible[s.key] ? s.color : "#71717a",
                border:     `1px solid ${visible[s.key] ? s.color : "#3f3f46"}`,
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
