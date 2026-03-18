import type { TransportDetail } from "@/domain/types";

type Props = {
  detail: TransportDetail;
};

const SUBS = [
  { key: "passages_tcl", label: "Passages TCL", weight: "50%", desc: "Bus/tram en approche (≤15 min)" },
  { key: "parcrelais",   label: "P+R (Parc Relais)", weight: "30%", desc: "Taux d'occupation" },
  { key: "velov",        label: "Vélo'v", weight: "20%", desc: "Taux de stations vides" },
] as const;

function pctBar(val: number | null) {
  if (val === null) return 0;
  return Math.min(100, val * 100);
}

function valLabel(val: number | null): string {
  if (val === null) return "N/A";
  return (val * 100).toFixed(0) + "%";
}

function barColor(val: number | null): string {
  if (val === null) return "var(--text-muted)";
  if (val <= 0.3) return "#22c55e";
  if (val <= 0.6) return "#f97316";
  return "#ef4444";
}

export default function ZoneTransportDetail({ detail }: Props) {
  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 flex items-center justify-between">
        <div className="text-[10px] font-semibold tracking-widest text-text-muted">
          DÉTAIL TRANSPORT TCL
        </div>
        <div className="text-[10px] text-text-muted">
          Score composite : <span className="font-semibold" style={{ color: barColor(detail.score) }}>
            {(detail.score * 100).toFixed(0)}%
          </span>
          {detail.fallback && (
            <span className="ml-1.5 rounded-sm bg-[#f9731622] px-1.5 py-px text-[9px] text-[#f97316]">
              fallback
            </span>
          )}
        </div>
      </div>

      {SUBS.map(({ key, label, weight, desc }) => {
        const val = detail[key as keyof TransportDetail] as number | null;
        return (
          <div key={key} className="mb-3">
            <div className="mb-0.5 flex justify-between text-[11px]">
              <span className="text-text-primary">
                {label}
                <span className="ml-1.5 text-[10px] text-text-muted">({weight})</span>
              </span>
              <span className="font-semibold" style={{ color: barColor(val) }}>
                {valLabel(val)}
              </span>
            </div>
            <div className="h-[5px] rounded-sm bg-bg-control">
              <div className="h-full rounded-sm transition-[width] duration-400 ease-out" style={{ width: `${pctBar(val)}%`, background: barColor(val) }} />
            </div>
            <div className="mt-0.5 text-[9px] text-text-muted">{desc}</div>
          </div>
        );
      })}
    </div>
  );
}
