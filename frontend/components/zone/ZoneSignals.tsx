import { scoreColor } from "@/domain/scoring";
import { SIGNAL_LABELS, SIGNAL_WEIGHTS } from "@/domain/constants";

type Props = {
  signals: Record<string, number>;
};

export default function ZoneSignals({ signals }: Props) {
  return (
    <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #2d3148" }}>
      <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>SIGNAUX</div>
      {Object.entries(signals)
        .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
        .map(([key, val]) => {
          const v   = val as number;
          const pct = Math.min(100, Math.abs(v) / 3 * 100);
          const c   = scoreColor(Math.min(100, 30 + Math.abs(v) * 25));
          const weight = SIGNAL_WEIGHTS[key] ?? 0;
          return (
            <div key={key} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: "#e2e8f0" }}>{SIGNAL_LABELS[key] ?? key}</span>
                <span style={{ color: c, fontWeight: 600 }}>
                  {v >= 0 ? "+" : ""}{v.toFixed(2)}σ · {weight}%
                </span>
              </div>
              <div style={{ height: 5, background: "#1e2235", borderRadius: 3 }}>
                <div style={{ height: "100%", width: `${pct}%`, background: c, borderRadius: 3 }} />
              </div>
            </div>
          );
        })}
    </div>
  );
}
