import { scoreColor } from "@/domain/scoring";
import { SIGNAL_LABELS } from "@/domain/constants";

type Props = {
  signals: Record<string, number>;
  weights?: Record<string, number>;
};

function intensityLabel(v: number): string {
  const abs = Math.abs(v);
  if (abs < 0.3) return "Normal";
  if (abs < 0.8) return "Légèrement élevé";
  if (abs < 1.5) return "Élevé";
  if (abs < 2.5) return "Très élevé";
  return "Critique";
}

function intensityColor(v: number): string {
  const abs = Math.abs(v);
  if (abs < 0.3) return "#71717a";
  if (abs < 0.8) return "#22c55e";
  if (abs < 1.5) return "#eab308";
  if (abs < 2.5) return "#f97316";
  return "#ef4444";
}

export default function ZoneSignals({ signals }: Omit<Props, "weights"> & { weights?: Record<string, number> }) {
  const sorted = Object.entries(signals).sort(([, a], [, b]) => Math.abs(b) - Math.abs(a));

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">FACTEURS DE TENSION</div>
      {sorted.map(([key, val]) => {
        const v   = val as number;
        const pct = Math.min(100, Math.abs(v) / 3 * 100);
        const c   = intensityColor(v);
        return (
          <div key={key} className="mb-3">
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-text-primary">{SIGNAL_LABELS[key] ?? key}</span>
              <span className="font-semibold" style={{ color: c }}>
                {intensityLabel(v)}
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
