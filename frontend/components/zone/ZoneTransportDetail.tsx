"use client";

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
    <div style={{
      background: "var(--bg-card)",
      borderRadius: 12,
      padding: 20,
      border: "1px solid var(--border)",
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: 14,
      }}>
        <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", fontWeight: 600 }}>
          DÉTAIL TRANSPORT TCL
        </div>
        <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
          Score composite : <span style={{ fontWeight: 600, color: barColor(detail.score) }}>
            {(detail.score * 100).toFixed(0)}%
          </span>
          {detail.fallback && (
            <span style={{
              marginLeft: 6,
              fontSize: 9,
              padding: "1px 5px",
              background: "#f9731622",
              color: "#f97316",
              borderRadius: 3,
            }}>
              fallback
            </span>
          )}
        </div>
      </div>

      {SUBS.map(({ key, label, weight, desc }) => {
        const val = detail[key as keyof TransportDetail] as number | null;
        return (
          <div key={key} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontSize: 11 }}>
              <span style={{ color: "var(--text-primary)" }}>
                {label}
                <span style={{ color: "var(--text-muted)", fontSize: 10, marginLeft: 6 }}>({weight})</span>
              </span>
              <span style={{ fontWeight: 600, color: barColor(val) }}>
                {valLabel(val)}
              </span>
            </div>
            <div style={{ height: 5, background: "var(--bg-control)", borderRadius: 3 }}>
              <div style={{
                height: "100%",
                width: `${pctBar(val)}%`,
                background: barColor(val),
                borderRadius: 3,
                transition: "width 0.4s ease-out",
              }} />
            </div>
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>{desc}</div>
          </div>
        );
      })}
    </div>
  );
}
