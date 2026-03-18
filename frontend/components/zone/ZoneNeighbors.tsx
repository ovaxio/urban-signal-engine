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
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">ZONES VOISINES</div>
      <div className="flex flex-wrap gap-2">
        {neighbors.map(n => (
          <Link key={n.zone_id} href={`/zones/${n.zone_id}${isSimMode ? `?sim=${simDate}` : ""}`}>
            <div className="cursor-pointer rounded-lg bg-bg-inner px-4 py-2.5" style={{ border: `1px solid ${scoreColor(n.urban_score)}44` }}>
              <div className="text-[11px] text-text-secondary">{n.zone_name}</div>
              <div className="text-xl font-bold" style={{ color: scoreColor(n.urban_score) }}>{n.urban_score}</div>
              <div className="mt-0.5 text-[9px]" style={{ color: scoreColor(n.urban_score) }}>{n.level}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
