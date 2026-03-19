"use client";

import type {
  PreEventReport,
  RiskWindowSummary,
  ReportRecommendation,
  SimulateZone,
  SimulateZoneHourly,
} from "@/domain/types";
import { scoreColor } from "@/domain/scoring";

/* ─── Helpers ──────────────────────────────────────────────────────────────── */

const SIGNAL_LABELS: Record<string, string> = {
  traffic: "Trafic",
  weather: "Météo",
  transport: "Transport",
  event: "Événement",
  incident: "Incidents",
};

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

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    high: "#22c55e",
    medium: "#eab308",
    low: "#f97316",
  };
  const labels: Record<string, string> = {
    high: "HAUTE",
    medium: "MOYENNE",
    low: "FAIBLE",
  };
  const c = colors[confidence] ?? "var(--text-muted)";
  return (
    <span
      className="rounded px-2 py-0.5 text-[10px] font-bold tracking-wider"
      style={{ background: `${c}1a`, color: c }}
    >
      CONFIANCE {labels[confidence] ?? confidence.toUpperCase()}
    </span>
  );
}

/* ─── Executive Summary ────────────────────────────────────────────────────── */

function ExecutiveSummary({ report }: { report: PreEventReport }) {
  const es = report.executive_summary;
  const cards = [
    { label: "RISQUE GLOBAL", value: es.overall_risk, color: scoreColor(es.overall_peak_score) },
    { label: "PIC ESTIMÉ", value: es.overall_peak_score, color: scoreColor(es.overall_peak_score) },
    { label: "ZONES CRITIQUES", value: es.critical_zones.length, color: "#ef4444" },
    { label: "CRÉNEAU PIC", value: `${es.peak_window.from}h-${es.peak_window.to}h`, color: "var(--text-primary)" },
  ];

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-border bg-bg-card px-3.5 py-2.5">
          <div className="mb-1 text-[9px] tracking-wider text-text-secondary">{c.label}</div>
          <div className="text-xl font-bold" style={{ color: c.color }}>
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Hourly Profile (mini bar chart) ──────────────────────────────────────── */

function HourlyProfile({ hourly }: { hourly: SimulateZoneHourly[] }) {
  const maxScore = Math.max(...hourly.map((h) => h.score), 1);

  return (
    <div className="flex items-end gap-px" style={{ height: 48 }}>
      {hourly.map((h) => {
        const pct = (h.score / 100) * 100;
        return (
          <div
            key={h.hour}
            title={`${h.hour}h — ${h.score} ${h.level}`}
            className="flex-1 rounded-t-sm transition-colors"
            style={{
              height: `${Math.max(pct, 2)}%`,
              background: scoreColor(h.score),
              opacity: 0.85,
              minWidth: 2,
            }}
          />
        );
      })}
    </div>
  );
}

function HourlyLabels({ hourly }: { hourly: SimulateZoneHourly[] }) {
  return (
    <div className="mt-0.5 flex gap-px">
      {hourly.map((h) => (
        <div
          key={h.hour}
          className="flex-1 text-center text-[8px] text-text-faint"
          style={{ minWidth: 2 }}
        >
          {h.hour % 3 === 0 ? `${h.hour}` : ""}
        </div>
      ))}
    </div>
  );
}

/* ─── Risk Windows ─────────────────────────────────────────────────────────── */

function RiskWindowsList({ windows }: { windows: RiskWindowSummary[] }) {
  if (!windows.length) {
    return (
      <div className="rounded-lg border border-border bg-bg-card p-4 text-center text-[13px] text-text-muted">
        Aucune fenêtre de risque détectée.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        FENÊTRES DE RISQUE ({windows.length})
      </div>
      <div className="flex flex-col gap-2">
        {windows.map((rw, i) => (
          <div
            key={i}
            className="rounded-md border-l-[3px] bg-bg-inner px-3 py-2"
            style={{ borderColor: scoreColor(rw.peak_score) }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-text-primary">
                  {rw.zone_name}
                </span>
                <LevelBadge level={rw.level} />
              </div>
              <span className="text-[12px] font-bold" style={{ color: scoreColor(rw.peak_score) }}>
                {rw.from}h — {rw.to}h
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-text-muted">
              <span>Pic {rw.peak_score}</span>
              <span>·</span>
              <span>Signal dominant : {SIGNAL_LABELS[rw.main_signal] ?? rw.main_signal}</span>
            </div>
            <div className="mt-1.5 text-[11px] text-text-secondary italic">
              {rw.recommendation}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Recommendations ──────────────────────────────────────────────────────── */

function Recommendations({ recommendations }: { recommendations: ReportRecommendation[] }) {
  if (!recommendations.length) return null;

  const levelColors = ["#22c55e", "#eab308", "#f97316", "#ef4444"];

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        RECOMMANDATIONS OPÉRATIONNELLES
      </div>
      <div className="flex flex-col gap-2">
        {recommendations.map((r, i) => (
          <div
            key={i}
            className="flex items-start gap-2.5 rounded-md bg-bg-inner px-3 py-2"
          >
            <div
              className="mt-0.5 size-2 shrink-0 rounded-full"
              style={{ background: levelColors[r.level] ?? "#888" }}
            />
            <div className="text-[12px] text-text-primary">{r.text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Weather Context ──────────────────────────────────────────────────────── */

function WeatherContext({ context }: { context: { summary: string; risk_modifier: string } }) {
  const modColors: Record<string, string> = {
    none: "#22c55e",
    low: "#eab308",
    medium: "#f97316",
    high: "#ef4444",
    unknown: "var(--text-muted)",
  };

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2 text-[11px] tracking-wide text-text-secondary">CONTEXTE MÉTÉO</div>
      <div className="flex items-start gap-2">
        <div
          className="mt-1 size-2 shrink-0 rounded-full"
          style={{ background: modColors[context.risk_modifier] ?? "var(--text-muted)" }}
        />
        <div className="text-[12px] text-text-primary">{context.summary}</div>
      </div>
    </div>
  );
}

/* ─── Zone Cards (with hourly profile) ─────────────────────────────────────── */

function ZoneCard({ zoneId, zone }: { zoneId: string; zone: SimulateZone }) {
  const zoneName =
    zoneId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="rounded-lg border border-border bg-bg-card p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[13px] font-semibold text-text-primary">{zoneName}</div>
        <LevelBadge level={zone.peak_level} />
      </div>

      <div className="mb-2.5 grid grid-cols-3 gap-2">
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">PIC</div>
          <div className="text-base font-bold" style={{ color: scoreColor(zone.peak_score) }}>
            {zone.peak_score}
          </div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">HEURE PIC</div>
          <div className="text-base font-bold text-text-primary">{zone.peak_hour}h</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">FENÊTRES</div>
          <div className="text-base font-bold text-text-primary">
            {zone.risk_windows.length}
          </div>
        </div>
      </div>

      <HourlyProfile hourly={zone.hourly} />
      <HourlyLabels hourly={zone.hourly} />

      {zone.risk_windows.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {zone.risk_windows.map((rw, i) => (
            <span
              key={i}
              className="rounded-sm px-1.5 py-0.5 text-[10px]"
              style={{
                background: `${scoreColor(rw.peak_score)}1a`,
                color: scoreColor(rw.peak_score),
              }}
            >
              {rw.from}h-{rw.to}h {rw.level}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Signals Breakdown ────────────────────────────────────────────────────── */

function SignalsBreakdown({
  breakdown,
}: {
  breakdown: Record<string, { dominant_signal: string; [k: string]: unknown }>;
}) {
  const zones = Object.entries(breakdown);
  if (!zones.length) return null;

  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        SIGNAUX DOMINANTS PAR ZONE
      </div>
      <div className="flex flex-col gap-1.5">
        {zones.map(([zid, data]) => {
          const sigKeys = ["traffic", "weather", "transport", "event", "incident"];
          const zscores = sigKeys.map((s) => ({
            signal: s,
            value: Number(data[`${s}_zscore`] ?? 0),
          }));
          const maxVal = Math.max(...zscores.map((z) => Math.abs(z.value)), 0.1);

          return (
            <div key={zid} className="rounded-md bg-bg-inner px-3 py-2">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-text-primary">
                  {zid.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
                <span className="rounded-sm bg-bg-control px-1.5 py-0.5 text-[10px] text-text-muted">
                  {SIGNAL_LABELS[data.dominant_signal] ?? data.dominant_signal}
                </span>
              </div>
              <div className="flex gap-1">
                {zscores.map((z) => (
                  <div key={z.signal} className="flex-1" title={`${SIGNAL_LABELS[z.signal]} ${z.value > 0 ? "+" : ""}${z.value}σ`}>
                    <div className="mb-0.5 flex items-end" style={{ height: 16 }}>
                      <div
                        className="w-full rounded-t-sm"
                        style={{
                          height: `${Math.max((Math.abs(z.value) / maxVal) * 100, 4)}%`,
                          background: z.value > 0 ? scoreColor(z.value > 2 ? 80 : z.value > 1 ? 60 : 45) : "#22c55e33",
                          minHeight: 1,
                        }}
                      />
                    </div>
                    <div className="text-center text-[8px] text-text-faint">
                      {SIGNAL_LABELS[z.signal]?.slice(0, 4)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main Component ───────────────────────────────────────────────────────── */

/* ─── Escalation Triggers ──────────────────────────────────────────────────── */

function EscalationTriggers({ triggers }: { triggers: { condition: string; action: string }[] }) {
  if (!triggers.length) return null;
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        TRIGGERS D&apos;ESCALADE
      </div>
      <div className="flex flex-col gap-2">
        {triggers.map((t, i) => (
          <div key={i} className="rounded-md bg-bg-inner px-3 py-2">
            <div className="text-[12px] font-semibold text-text-primary">
              SI : {t.condition}
            </div>
            <div className="mt-0.5 text-[11px] text-text-secondary">
              ALORS : {t.action}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── DPS Info ─────────────────────────────────────────────────────────────── */

function DpsSection({ dps }: { dps: { categorie: string; description: string; ratio: string; staffing_estimate: string; zones_tendu: number } }) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="mb-2.5 text-[11px] tracking-wide text-text-secondary">
        DIMENSIONNEMENT DPS
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">CATÉGORIE</div>
          <div className="text-sm font-bold text-text-primary">{dps.categorie}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">EFFECTIF ESTIMÉ</div>
          <div className="text-sm font-bold text-text-primary">{dps.staffing_estimate}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">RATIO</div>
          <div className="text-[11px] text-text-secondary">{dps.ratio}</div>
        </div>
        <div>
          <div className="text-[9px] tracking-wide text-text-muted">ZONES TENDU+</div>
          <div className="text-sm font-bold text-text-primary">{dps.zones_tendu}</div>
        </div>
      </div>
      <div className="mt-2 text-[10px] text-text-muted">{dps.description}</div>
    </div>
  );
}

/* ─── Main Component ───────────────────────────────────────────────────────── */

export default function PreEventReportView({ report }: { report: PreEventReport }) {
  const sortedZones = Object.entries(report.zones_analysis).sort(
    ([, a], [, b]) => b.peak_score - a.peak_score
  );

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="rounded-lg border border-border bg-bg-card p-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="mb-1 text-base font-bold text-text-primary">
              Rapport pré-événement — {report.event.name}
            </div>
            <div className="text-xs text-text-muted">
              Simulation du {report.event.date} · {Object.keys(report.zones_analysis).length} zones analysées
            </div>
          </div>
          <ConfidenceBadge confidence={report.data_confidence} />
        </div>
      </div>

      {/* BLUF */}
      <div className="rounded-lg border-l-[3px] bg-bg-card px-4 py-3" style={{ borderColor: scoreColor(report.executive_summary.overall_peak_score) }}>
        <div className="text-[13px] leading-relaxed text-text-primary">{report.bluf}</div>
      </div>

      <ExecutiveSummary report={report} />
      <Recommendations recommendations={report.recommendations} />
      <EscalationTriggers triggers={report.escalation_triggers} />
      <RiskWindowsList windows={report.risk_windows_summary} />
      <DpsSection dps={report.dps} />
      <WeatherContext context={report.weather_context} />

      {/* Zone cards */}
      <div>
        <div className="mb-2 text-[11px] tracking-wide text-text-secondary">
          PROFIL HORAIRE PAR ZONE ({sortedZones.length})
        </div>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-2.5">
          {sortedZones.map(([id, zone]) => (
            <ZoneCard key={id} zoneId={id} zone={zone} />
          ))}
        </div>
      </div>

      <SignalsBreakdown breakdown={report.signals_breakdown} />

      <div className="pt-2 text-center text-[10px] text-text-faint">
        Rapport généré par Urban Signal Engine le{" "}
        {report.generated_at.replace("T", " ").slice(0, 16)} · {report.next_update}
      </div>
    </div>
  );
}
