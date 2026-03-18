import { scoreColor } from "@/domain/scoring";
import { SIGNAL_LABELS } from "@/domain/constants";

type Props = {
  signals: Record<string, number>;
  weights?: Record<string, number>;
};

export default function ZoneSignals({ signals, weights }: Props) {
  const sorted = Object.entries(signals).sort(([, a], [, b]) => Math.abs(b) - Math.abs(a));

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">SIGNAUX</div>
      {sorted.map(([key, val]) => {
        const v   = val as number;
        const pct = Math.min(100, Math.abs(v) / 3 * 100);
        const c   = scoreColor(Math.min(100, 30 + Math.abs(v) * 25));
        const weight = weights?.[key] ?? 0;
        return (
          <div key={key} className="mb-3">
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-text-primary">{SIGNAL_LABELS[key] ?? key}</span>
              <span className="font-semibold" style={{ color: c }}>
                {v >= 0 ? "+" : ""}{v.toFixed(2)}σ · {weight}%
              </span>
            </div>
            <div className="h-[5px] rounded-sm bg-bg-control">
              <div className="h-full rounded-sm" style={{ width: `${pct}%`, background: c }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
