import type { ImpactReport, ImpactZone, Alert } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";

function Delta({ value }: { value: number | null }) {
  if (value == null) return null;
  const sign = value > 0 ? "+" : "";
  const color = value > 5 ? "#ef4444" : value > 0 ? "#f97316" : "#22c55e";
  return (
    <span style={{ color, fontWeight: 600, fontSize: 13 }}>
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
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.08em",
        padding: "2px 8px",
        borderRadius: 4,
        background: `${c}1a`,
        color: c,
      }}
    >
      {level}
    </span>
  );
}

function SummaryCards({ report }: { report: ImpactReport }) {
  const s = report.summary;
  const cards = [
    { label: "SCORE MOYEN", value: s.global_avg_score, color: scoreColor(s.global_avg_score) },
    { label: "PIC", value: s.global_peak_score, color: scoreColor(s.global_peak_score) },
    { label: "ALERTES CRITIQUE", value: s.alerts_critique, color: "#ef4444" },
    { label: "ALERTES TENDU", value: s.alerts_tendu, color: "#f97316" },
    { label: "ZONES ANALYSÉES", value: s.zones_analyzed, color: "var(--text-primary)" },
    { label: "RELEVÉS", value: s.total_data_points, color: "var(--text-primary)" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 8 }}>
      {cards.map((c) => (
        <div
          key={c.label}
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "10px 14px",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-secondary)", letterSpacing: "0.08em", marginBottom: 4 }}>
            {c.label}
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: c.color }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}

function BaselineComparison({ report }: { report: ImpactReport }) {
  const s = report.summary;
  if (s.baseline_avg_score == null) return null;

  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", marginBottom: 10 }}>
        COMPARAISON AVEC PÉRIODE DE RÉFÉRENCE
      </div>
      <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Référence</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: scoreColor(s.baseline_avg_score) }}>
            {s.baseline_avg_score}
          </div>
        </div>
        <div style={{ fontSize: 20, color: "var(--text-muted)" }}>→</div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Événement</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: scoreColor(s.global_avg_score) }}>
            {s.global_avg_score}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>Delta</div>
          <div style={{ fontSize: 18 }}>
            <Delta value={s.delta_vs_baseline} />
          </div>
        </div>
      </div>
      {report.baseline_period && (
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 8 }}>
          Période de référence : {report.baseline_period.start.split("T")[0]} → {report.baseline_period.end.split("T")[0]}
        </div>
      )}
    </div>
  );
}

function TopZones({ report }: { report: ImpactReport }) {
  const zones = report.top_impacted_zones;
  if (!zones.length) return null;

  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", marginBottom: 10 }}>
        TOP ZONES IMPACTÉES
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {zones.map((z, i) => (
          <div
            key={z.zone_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "8px 12px",
              borderRadius: 6,
              background: "var(--bg-inner)",
            }}
          >
            <div
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                background: scoreColor(z.peak_score),
                color: "#fff",
                fontSize: 11,
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {i + 1}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                {z.zone_name}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                Moy. {z.avg_score} · Pic {z.peak_score}
              </div>
            </div>
            <LevelBadge level={z.peak_level} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ZoneDetail({ zoneId, zone }: { zoneId: string; zone: ImpactZone }) {
  const levels = zone.level_distribution;
  const total = Object.values(levels).reduce((a, b) => a + b, 0);

  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 14,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
          {zone.zone_name}
        </div>
        <LevelBadge level={zone.peak_level} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.06em" }}>MOY.</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: scoreColor(zone.avg_score) }}>{zone.avg_score}</div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.06em" }}>PIC</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: scoreColor(zone.peak_score) }}>{zone.peak_score}</div>
        </div>
        <div>
          <div style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.06em" }}>DELTA</div>
          <div style={{ fontSize: 16 }}><Delta value={zone.delta_vs_baseline} /></div>
        </div>
      </div>

      {/* Level distribution bar */}
      {total > 0 && (
        <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", marginBottom: 8 }}>
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

      {/* Signal breakdown */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 10, color: "var(--text-muted)" }}>
        {Object.entries(zone.signal_averages_normalized).map(([sig, val]) => (
          <span key={sig} style={{ background: "var(--bg-control)", padding: "2px 6px", borderRadius: 3 }}>
            {sig} {val > 0 ? "+" : ""}{val.toFixed(2)}σ
          </span>
        ))}
      </div>

      <div style={{ fontSize: 10, color: "var(--text-faint)", marginTop: 6 }}>
        {zone.data_points} relevés · {zone.readings_tendu} TENDU · {zone.readings_critique} CRITIQUE
      </div>
    </div>
  );
}

function AlertsList({ alerts }: { alerts: Alert[] }) {
  if (!alerts.length) return null;
  const emojis: Record<string, string> = { CRITIQUE: "\u{1f534}", TENDU: "\u{1f7e0}", CALME: "\u{1f7e2}" };

  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", marginBottom: 10 }}>
        ALERTES DÉCLENCHÉES ({alerts.length})
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 200, overflowY: "auto" }}>
        {alerts.map((a, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              fontSize: 12,
              padding: "4px 8px",
              borderRadius: 4,
              background: "var(--bg-inner)",
            }}
          >
            <span>{emojis[a.alert_type] ?? ""}</span>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{a.zone_name}</span>
            <span style={{ color: "var(--text-muted)" }}>
              {a.prev_score} → {a.urban_score}
            </span>
            <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-faint)" }}>
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
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 16,
        }}
      >
        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
          {report.event_name
            ? `Rapport d'impact — ${report.event_name}`
            : "Rapport d'impact — Période personnalisée"}
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
          {report.period.start.split("T")[0]} → {report.period.end.split("T")[0]}
        </div>
      </div>

      <SummaryCards report={report} />
      <BaselineComparison report={report} />
      <TopZones report={report} />

      {/* All zones detail */}
      <div>
        <div
          style={{
            fontSize: 11,
            color: "var(--text-secondary)",
            letterSpacing: "0.06em",
            marginBottom: 8,
          }}
        >
          DÉTAIL PAR ZONE ({sortedZones.length})
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 10,
          }}
        >
          {sortedZones.map(([id, zone]) => (
            <ZoneDetail key={id} zoneId={id} zone={zone} />
          ))}
        </div>
      </div>

      <AlertsList alerts={report.alerts} />

      {/* Footer */}
      <div style={{ fontSize: 10, color: "var(--text-faint)", textAlign: "center", paddingTop: 8 }}>
        Rapport généré par Urban Signal Engine · Données historiques issues de {report.summary.total_data_points} relevés
      </div>
    </div>
  );
}
