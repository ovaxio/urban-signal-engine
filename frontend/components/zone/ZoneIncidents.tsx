import type { IncidentEvent } from "@/domain/types";
import { EVENT_ICONS, EVENT_TYPE_LABELS } from "@/domain/constants";

type Props = {
  events: IncidentEvent[];
};

export default function ZoneIncidents({ events }: Props) {
  if (events.length === 0) return null;

  return (
    <div className="rounded-xl border border-[#ef444433] bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">PERTURBATIONS EN COURS</div>
      <div className="flex flex-col gap-2">
        {events.map((ev, i) => (
          <div key={i} className="flex items-start gap-2.5 rounded-lg bg-bg-inner px-3 py-2.5" style={{ borderLeft: `3px solid ${ev.ends_soon ? "#f97316" : "#ef4444"}` }}>
            <span className="shrink-0 text-base">{EVENT_ICONS[ev.type] ?? "⚠️"}</span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-medium text-text-primary">{ev.label}</div>
              {(ev.detail || ev.direction) && (
                <div className="mt-0.5 truncate text-[10px] text-text-secondary">
                  {ev.detail}{ev.detail && ev.direction ? " · " : ""}{ev.direction}
                </div>
              )}
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                {(ev.delay_min ?? 0) > 0 && (
                  <span className="rounded-sm border border-[#f9731633] bg-[#f9731611] px-1.5 py-px text-[9px] text-[#f97316]">+{ev.delay_min} min</span>
                )}
                {ev.end && (
                  <span className="text-[10px]" style={{ color: ev.ends_soon ? "#f97316" : "var(--text-muted)" }}>
                    {ev.ends_soon ? `⏳ Fin prévue ${ev.end}` : `Jusqu'au ${ev.end}`}
                  </span>
                )}
              </div>
            </div>
            <span className="shrink-0 rounded bg-bg-control px-1.5 py-0.5 text-[9px]" style={{ color: ev.weight >= 2.0 ? "#ef4444" : "var(--text-secondary)" }}>
              {EVENT_TYPE_LABELS[ev.type] ?? ev.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
