"use client";

import type { ZoneDetail } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import { useCountUp } from "@/hooks/useCountUp";

type Props = {
  zone: ZoneDetail;
  simDate?: string | null;
};

const REC_COLORS: Record<number, string> = {
  0: "var(--text-muted)",
  1: "#f59e0b",
  2: "#f97316",
  3: "#ef4444",
};

export default function ZoneScoreHeader({ zone, simDate }: Props) {
  const col = scoreColor(zone.urban_score);
  const isSimMode = !!simDate;
  const displayScore = useCountUp(zone.urban_score, 700);

  const delta = zone.delta_vs_typical;
  const hasDelta = delta != null && zone.delta_label;
  const deltaSign = delta != null && delta > 0 ? "+" : "";
  const deltaColor = delta != null ? (delta > 5 ? "#ef4444" : delta < -5 ? "#22c55e" : "var(--text-muted)") : undefined;

  const rec = zone.recommendation;
  const recColor = rec ? REC_COLORS[rec.level] ?? "var(--text-muted)" : undefined;

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-bg-card p-6" style={{ border: `1px solid ${col}33` }}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-[200px] flex-1">
          <div className="text-[26px] font-extrabold">{zone.zone_name}</div>
          {!isSimMode && (
            <div className="mt-1 text-xs text-text-muted">
              {"\u03c6"} = {zone.components.phi.toFixed(2)} · {new Date(zone.timestamp).toLocaleTimeString("fr-FR", { timeZone: "Europe/Paris" })}
            </div>
          )}
          {isSimMode && (
            <div className="mt-1 text-xs text-[#f97316]">
              Simulation · {simDate} · {"\u03c6"} = {zone.components.phi.toFixed(2)}
            </div>
          )}
          <div className="mt-3 text-[13px] leading-relaxed text-text-secondary">{zone.explanation}</div>
        </div>
        <div className="ml-4 shrink-0 text-right">
          <div className="text-[56px] font-black leading-none" style={{ color: col }}>{displayScore}</div>
          <div className="mt-1 text-[13px] font-bold" style={{ color: col }}>{zone.level}</div>
          {hasDelta && (
            <div className="mt-1 text-[11px] font-medium" style={{ color: deltaColor }}>
              {deltaSign}{delta.toFixed(0)} vs moyenne
            </div>
          )}
        </div>
      </div>

      {/* Delta context + Recommendation */}
      {!isSimMode && (hasDelta || rec) && (
        <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border)] pt-3">
          {hasDelta && (
            <span className="rounded px-2 py-0.5 text-[11px] font-medium" style={{ color: deltaColor, background: `${deltaColor}11`, border: `1px solid ${deltaColor}33` }}>
              {zone.delta_label}
            </span>
          )}
          {rec && (
            <span className="text-[12px]" style={{ color: recColor }}>
              {rec.action}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
