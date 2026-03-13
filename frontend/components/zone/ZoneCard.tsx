import Link from "next/link";
import type { ZoneSummary } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import ScoreBar from "@/components/ui/ScoreBar";

type Props = {
  zone: ZoneSummary;
  simDate?: string;
};

export default function ZoneCard({ zone, simDate }: Props) {
  const isAlert = zone.urban_score >= 55;
  const col = scoreColor(zone.urban_score);
  const href = `/zones/${zone.zone_id}${simDate ? `?sim=${simDate}` : ""}`;

  return (
    <Link href={href}>
      <div style={{
        background: isAlert ? `${col}0d` : "#1a1d27",
        border: `1px solid ${col}${isAlert ? "66" : "33"}`,
        borderRadius: 10,
        padding: "14px 16px",
        cursor: "pointer",
        boxShadow: isAlert ? `0 0 14px ${col}22` : "none",
        transition: "box-shadow 0.3s",
        position: "relative",
        minWidth: 0,
      }}>
        <ScoreBar pct={zone.urban_score} color={col} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}>{zone.zone_name}</div>
          {isAlert && <div style={{ width: 6, height: 6, borderRadius: "50%", background: col, boxShadow: `0 0 5px ${col}`, flexShrink: 0 }} />}
        </div>

        <div style={{ fontSize: 32, fontWeight: 800, color: col, lineHeight: 1 }}>{zone.urban_score}</div>
        <div style={{ fontSize: 10, color: col, marginTop: 3, fontWeight: 700, letterSpacing: "0.05em" }}>{zone.level}</div>

        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 2 }}>
          {(zone.top_causes ?? []).length > 0
            ? zone.top_causes.slice(0, 2).map((c, i) => (
                <div key={i} style={{ fontSize: 9, color: "#94a3b8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>▸ {c}</div>
              ))
            : <div style={{ fontSize: 9, color: "#94a3b8", fontStyle: "italic" }}>Conditions normales</div>
          }
        </div>
      </div>
    </Link>
  );
}
