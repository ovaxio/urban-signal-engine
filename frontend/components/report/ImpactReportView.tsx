import type { ImpactReport, ImpactZone, Alert } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";

const SIGNAL_LABELS: Record<string, string> = {
  traffic:   "Trafic",
  weather:   "Météo",
  event:     "Événement",
  transport: "Transport TCL",
  incident:  "Incidents",
};

function Delta({ value }: { value: number | null }) {
  if (value == null) return null;
  const sign = value > 0 ? "+" : "";
  const color = value > 5 ? "#ef4444" : value > 0 ? "#f97316" : "#22c55e";
  return (
    <span className="text-[13px] font-semibold" style={{ color }}>
      {sign}{value} pts
    </span>
  );
}

function LevelBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    CALME: "#22c55e",
    "MODÉRÉ": "#eab308",
    TENDU: "#f97316",
    CRITIQUE: "#ef4444",
  };
  const c = colors[level] ?? "var(--text-muted)";
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-bold tracking-wider"
      style={{ background: `${c}1a`, color: c }}
    >
      {level}
    </span>
  );
}

function SummaryCards({ report }: { report: ImpactReport }) {
  const s = report.summary;
  const cards = [
    { label: "SCORE MOYEN", value: s.global_avg_score, color: scoreColor(s.global_avg_score) },
    { label: "PIC DE TENSION", value: s.global_peak_score, color: scoreColor(s.global_peak_score) },
    { label: "ALERTES CRITIQUES", value: s.alerts_critique, color: "#ef4444" },
    { label: "ALERTES TENDUES", value: s.alerts_tendu, color: "#f97316" },
    { label: "ZONES SURVEILLÉES", value: s.zones_analyzed, color: "var(--text-primary)" },
    { label: "MESURES COLLECTÉES", value: s.total_data_points, color: "var(--text-primary)" },
  ];

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-2">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-border bg-bg-card px-3.5 py-2.5">
          <div className="mb-1 text-[9px] tracking-wider text-text-secondary">{c.label}</div>
          <div className="text-xl font-bold" style={{ color: c.color }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}

function BaselineComparison({ report }: { report: ImpactReport }) {
  const s = report.summary;
  if (s.baseline_avg_score == null) return null;

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        COMPARAISON AVEC UNE PÉRIODE SANS ÉVÉNEMENT
      </div>
      <div className="flex flex-wrap items-center gap-6">
        <div>
          <div className="text-[10px] text-text-muted">Sans événement</div>
          <div className="text-lg font-bold" style={{ color: scoreColor(s.baseline_avg_score) }}>
            {s.baseline_avg_score}
          </div>
        </div>
        <div className="text-xl text-text-muted">→</div>
        <div>
          <div className="text-[10px] text-text-muted">Pendant l'événement</div>
          <div className="text-lg font-bold" style={{ color: scoreColor(s.global_avg_score) }}>
            {s.global_avg_score}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-text-muted">Hausse</div>
          <div className="text-lg"><Delta value={s.delta_vs_baseline} /></div>
        </div>
      </div>
      {report.baseline_period && (
        <div className="mt-2 text-[10px] text-text-muted">
          Période de comparaison (sans événement) : {report.baseline_period.start.split("T")[0]} → {report.baseline_period.end.split("T")[0]}
        </div>
      )}
    </div>
  );
}

function TopZones({ report }: { report: ImpactReport }) {
  const zones = report.top_impacted_zones;
  if (!zones.length) return null;

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        ZONES LES PLUS TOUCHÉES
      </div>
      <div className="flex flex-col gap-2">
        {zones.map((z, i) => (
          <div key={z.zone_id} className="flex items-center gap-3 rounded-md bg-bg-inner px-3 py-2">
            <div
              className="flex size-6 items-center justify-center rounded-full text-[11px] font-bold text-white"
              style={{ background: scoreColor(z.peak_score) }}
            >
              {i + 1}
            </div>
            <div className="flex-1">
              <div className="text-[13px] font-semibold text-text-primary">{z.zone_name}</div>
              <div className="text-[11px] text-text-muted">Moy. {z.avg_score} · Pic {z.peak_score}</div>
            </div>
            <LevelBadge level={z.peak_level} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ZoneDetailCard({ zoneId, zone }: { zoneId: string; zone: ImpactZone }) {
  const levels = zone.level_distribution;
  const total = Object.values(levels).reduce((a, b) => a + b, 0);

  return (
    <div className="rounded-lg border border-border bg-bg-card p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[13px] font-semibold text-text-primary">{zone.zone_name}</div>
        <LevelBadge level={zone.peak_level} />
      </div>

      <div className="mb-2.5 grid grid-cols-3 gap-2">
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">MOY.</div>
          <div className="text-base font-bold" style={{ color: scoreColor(zone.avg_score) }}>{zone.avg_score}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">MAXI</div>
          <div className="text-base font-bold" style={{ color: scoreColor(zone.peak_score) }}>{zone.peak_score}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">ÉCART</div>
          <div className="text-base"><Delta value={zone.delta_vs_baseline} /></div>
        </div>
      </div>

      {total > 0 && (
        <div className="mb-2 flex h-1.5 overflow-hidden rounded-sm">
          {(["CALME", "MODÉRÉ", "TENDU", "CRITIQUE"] as const).map((l) => {
            const pct = ((levels[l] ?? 0) / total) * 100;
            if (pct === 0) return null;
            return (
              <div
                key={l}
                style={{
                  width: `${pct}%`,
                  background: scoreColor(l === "CALME" ? 10 : l === "MODÉRÉ" ? 45 : l === "TENDU" ? 60 : 80),
                }}
              />
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap gap-2 text-[10px] text-text-muted">
        {Object.entries(zone.signal_averages_normalized).map(([sig, val]) => {
          const abs = Math.abs(val);
          const intensity = abs < 0.3 ? "normal" : abs < 0.8 ? "légèrement élevé" : abs < 1.5 ? "élevé" : "critique";
          return (
            <span key={sig} className="rounded-sm bg-bg-control px-1.5 py-0.5">
              {SIGNAL_LABELS[sig] ?? sig} — {intensity}
            </span>
          );
        })}
      </div>

      <div className="mt-1.5 text-[10px] text-text-faint">
        {zone.data_points} relevés · {zone.readings_tendu} créneaux tendus · {zone.readings_critique} critiques
      </div>
    </div>
  );
}

function AlertsList({ alerts }: { alerts: Alert[] }) {
  if (!alerts.length) return null;
  const emojis: Record<string, string> = { CRITIQUE: "\u{1f534}", TENDU: "\u{1f7e0}", CALME: "\u{1f7e2}" };

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        ALERTES ENREGISTRÉES ({alerts.length})
      </div>
      <div className="flex max-h-[200px] flex-col gap-1 overflow-y-auto">
        {alerts.map((a, i) => (
          <div key={i} className="flex items-center gap-2 rounded bg-bg-inner px-2 py-1 text-xs">
            <span>{emojis[a.alert_type] ?? ""}</span>
            <span className="font-semibold text-text-primary">{a.zone_name}</span>
            <span className="text-text-muted">{a.prev_score} → {a.urban_score}</span>
            <span className="ml-auto text-[10px] text-text-faint">
              {a.ts.replace("T", " ").slice(0, 16)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ImpactReportView({ report }: { report: ImpactReport }) {
  const zones = report.zones;
  const sortedZones = Object.entries(zones).sort(
    ([, a], [, b]) => b.avg_score - a.avg_score
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-border bg-bg-card p-4">
        <div className="mb-1 text-base font-bold text-text-primary">
          {report.event_name
            ? `Rapport d'impact — ${report.event_name}`
            : "Rapport d'impact — Période personnalisée"}
        </div>
        <div className="text-xs text-text-muted">
          {report.period.start.split("T")[0]} → {report.period.end.split("T")[0]}
        </div>
      </div>

      <SummaryCards report={report} />
      <BaselineComparison report={report} />
      <TopZones report={report} />

      <div>
        <div className="mb-2 text-[11px] tracking-wide text-text-secondary">
          ANALYSE ZONE PAR ZONE ({sortedZones.length})
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-2.5">
          {sortedZones.map(([id, zone]) => (
            <ZoneDetailCard key={id} zoneId={id} zone={zone} />
          ))}
        </div>
      </div>

      <AlertsList alerts={report.alerts} />

      <div className="pt-2 text-center text-[10px] text-text-faint">
        Rapport généré par Urban Signal Engine · Basé sur {report.summary.total_data_points} mesures collectées
      </div>
    </div>
  );
}
