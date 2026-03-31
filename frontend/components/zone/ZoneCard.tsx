import Link from "next/link";
import type { ZoneSummary } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import { SIGNAL_LABELS } from "@/domain/constants";
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
      <div
        className="zone-card relative min-w-0 cursor-pointer rounded-[10px] px-4 py-3.5"
        style={{
          background: isAlert ? `${col}0d` : "var(--bg-card)",
          border: `1px solid ${col}${isAlert ? "66" : "33"}`,
          boxShadow: isAlert ? `0 0 14px ${col}22` : "none",
        }}
      >
        <ScoreBar pct={zone.urban_score} color={col} />

        <div className="flex items-start justify-between">
          <div className="mb-1 min-w-0 truncate text-[11px] text-text-secondary">{zone.zone_name}</div>
          {isAlert && <div className="size-1.5 shrink-0 rounded-full" style={{ background: col, boxShadow: `0 0 5px ${col}` }} />}
        </div>

        <div className="text-[32px] font-extrabold leading-none" style={{ color: col }}>{zone.urban_score}</div>
        <div className="mt-0.5 text-[10px] font-bold tracking-wide" style={{ color: col }}>{zone.level}</div>

        <div className="mt-2.5 flex flex-col gap-0.5">
          {(zone.top_causes ?? []).length > 0
            ? zone.top_causes.slice(0, 2).map((c, i) => (
                <div key={i} className="truncate text-[9px] text-text-secondary">▸ {SIGNAL_LABELS[c] ?? c}</div>
              ))
            : <div className="text-[9px] italic text-text-secondary">Conditions normales</div>
          }
        </div>
      </div>
    </Link>
  );
}
