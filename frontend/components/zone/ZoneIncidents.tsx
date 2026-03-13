import type { IncidentEvent } from "@/domain/types";
import { EVENT_ICONS, EVENT_TYPE_LABELS } from "@/domain/constants";

type Props = {
  events: IncidentEvent[];
};

export default function ZoneIncidents({ events }: Props) {
  if (events.length === 0) return null;

  return (
    <div style={{ background: "#1a1d27", borderRadius: 12, padding: 20, border: "1px solid #ef444433" }}>
      <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>PERTURBATIONS EN COURS</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {events.map((ev, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", background: "#13161f", borderRadius: 8, borderLeft: `3px solid ${ev.ends_soon ? "#f97316" : "#ef4444"}` }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>{EVENT_ICONS[ev.type] ?? "⚠️"}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: "#e2e8f0", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ev.label}</div>
              {(ev.detail || ev.direction) && (
                <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {ev.detail}{ev.detail && ev.direction ? " · " : ""}{ev.direction}
                </div>
              )}
              <div style={{ display: "flex", gap: 6, marginTop: 3, flexWrap: "wrap", alignItems: "center" }}>
                {(ev.delay_min ?? 0) > 0 && (
                  <span style={{ fontSize: 9, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", padding: "1px 5px", borderRadius: 3 }}>+{ev.delay_min} min</span>
                )}
                {ev.end && (
                  <span style={{ fontSize: 10, color: ev.ends_soon ? "#f97316" : "#64748b" }}>
                    {ev.ends_soon ? `⏳ Fin prévue ${ev.end}` : `Jusqu'au ${ev.end}`}
                  </span>
                )}
              </div>
            </div>
            <span style={{ fontSize: 9, color: ev.weight >= 2.0 ? "#ef4444" : "#94a3b8", background: "#1e2235", padding: "2px 6px", borderRadius: 4, flexShrink: 0 }}>
              {EVENT_TYPE_LABELS[ev.type] ?? ev.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
