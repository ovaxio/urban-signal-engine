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
    <div style={{ background: "#1a1d27", borderRadius: 12, padding: 24, border: `1px solid ${col}33`, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 200 }}>
        <div style={{ fontSize: 26, fontWeight: 800 }}>{zone.zone_name}</div>
        {!isSimMode && (
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
            φ = {zone.components.phi.toFixed(2)} · {new Date(zone.timestamp).toLocaleTimeString("fr-FR", { timeZone: "Europe/Paris" })}
          </div>
        )}
        {isSimMode && (
          <div style={{ fontSize: 12, color: "#f97316", marginTop: 4 }}>
            Simulation · {simDate} · φ = {zone.components.phi.toFixed(2)}
          </div>
        )}
        <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 12, lineHeight: 1.7 }}>{zone.explanation}</div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, marginLeft: 16 }}>
        <div style={{ fontSize: 56, fontWeight: 900, color: col, lineHeight: 1 }}>{displayScore}</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: col, marginTop: 4 }}>{zone.level}</div>
      </div>
    </div>
  );
}
