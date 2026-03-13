import Link from "next/link";
import type { ZoneNeighbor } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";

type Props = {
  neighbors: ZoneNeighbor[];
  simDate?: string | null;
};

export default function ZoneNeighbors({ neighbors, simDate }: Props) {
  const isSimMode = !!simDate;

  return (
    <div style={{ background: "var(--bg-card)", borderRadius: 12, padding: 20, border: "1px solid var(--border)" }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>ZONES VOISINES</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {neighbors.map(n => (
          <Link key={n.zone_id} href={`/zones/${n.zone_id}${isSimMode ? `?sim=${simDate}` : ""}`}>
            <div style={{ padding: "10px 16px", background: "var(--bg-inner)", borderRadius: 8, border: `1px solid ${scoreColor(n.urban_score)}44`, cursor: "pointer" }}>
              <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>{n.zone_name}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: scoreColor(n.urban_score) }}>{n.urban_score}</div>
              <div style={{ fontSize: 9, color: scoreColor(n.urban_score), marginTop: 2 }}>{n.level}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
