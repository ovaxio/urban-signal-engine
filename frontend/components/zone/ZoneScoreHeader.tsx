"use client";

import type { ZoneDetail } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import { useCountUp } from "@/hooks/useCountUp";

type Props = {
  zone: ZoneDetail;
  simDate?: string | null;
};

export default function ZoneScoreHeader({ zone, simDate }: Props) {
  const col = scoreColor(zone.urban_score);
  const isSimMode = !!simDate;
  const displayScore = useCountUp(zone.urban_score, 700);

  return (
    <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl bg-bg-card p-6" style={{ border: `1px solid ${col}33` }}>
      <div className="min-w-[200px] flex-1">
        <div className="text-[26px] font-extrabold">{zone.zone_name}</div>
        {!isSimMode && (
          <div className="mt-1 text-xs text-text-muted">
            φ = {zone.components.phi.toFixed(2)} · {new Date(zone.timestamp).toLocaleTimeString("fr-FR", { timeZone: "Europe/Paris" })}
          </div>
        )}
        {isSimMode && (
          <div className="mt-1 text-xs text-[#f97316]">
            Simulation · {simDate} · φ = {zone.components.phi.toFixed(2)}
          </div>
        )}
        <div className="mt-3 text-[13px] leading-relaxed text-text-secondary">{zone.explanation}</div>
      </div>
      <div className="ml-4 shrink-0 text-right">
        <div className="text-[56px] font-black leading-none" style={{ color: col }}>{displayScore}</div>
        <div className="mt-1 text-[13px] font-bold" style={{ color: col }}>{zone.level}</div>
      </div>
    </div>
  );
}
