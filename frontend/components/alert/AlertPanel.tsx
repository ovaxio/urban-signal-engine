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
    <div className="overflow-hidden rounded-[10px] border border-border bg-bg-card">
      <button
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls="alert-list"
        className="flex w-full cursor-pointer select-none items-center gap-2 border-none bg-transparent px-3.5 py-2.5 font-inherit text-inherit"
      >
        <span className="flex-1 text-left text-[10px] font-semibold tracking-widest text-text-muted">
          ALERTES
        </span>
        {unread > 0 && (
          <span className="rounded-[10px] border border-[#ef444433] bg-[#ef444422] px-1.5 py-px text-[9px] font-bold text-[#ef4444]">
            {unread}
          </span>
        )}
        <span className="text-[10px] text-text-faint" aria-hidden="true">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div id="alert-list" role="region" aria-label="Liste des alertes" className="border-t border-border">
          {alerts.length === 0 ? (
            <div className="p-3.5 text-center text-[11px] text-text-secondary">
              Aucune alerte enregistrée.
            </div>
          ) : (
            alerts.map((a, i) => {
              const meta = ALERT_META[a.alert_type] ?? ALERT_META.TENDU;
              const dir  = a.urban_score > a.prev_score ? "↑" : "↓";
              return (
                <div
                  key={`${a.ts}-${a.zone_id}`}
                  className="flex items-center gap-2.5 px-3.5 py-2"
                  style={{
                    borderBottom: i < alerts.length - 1 ? "1px solid var(--bg-control)" : undefined,
                    background: i === 0 ? `${meta.color}08` : undefined,
                  }}
                >
                  <span className="text-[13px]">{meta.emoji}</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[11px] font-semibold text-text-primary">
                      {a.zone_name}
                    </div>
                    <div className="mt-px text-[9px] text-text-faint">
                      {meta.label} · {a.prev_score} {dir} {a.urban_score}
                    </div>
                  </div>
                  <div className="shrink-0 text-[10px] text-text-muted">
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
