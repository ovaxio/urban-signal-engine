import Link from "next/link";
import { fetchDetail, fetchForecast, fetchSimulationDetail } from "@/lib/api";
import type { ZoneDetail, Forecast } from "@/domain/types";

import ZoneScoreHeader    from "@/components/zone/ZoneScoreHeader";
import ZoneSignals        from "@/components/zone/ZoneSignals";
import ZoneComponentsGrid from "@/components/zone/ZoneComponentsGrid";
import ZoneForecast       from "@/components/zone/ZoneForecast";
import ZoneNeighbors      from "@/components/zone/ZoneNeighbors";
import ZoneIncidents      from "@/components/zone/ZoneIncidents";
import SimBanner          from "@/components/layout/SimBanner";
import ZoneHistoryChart   from "@/components/chart/ZoneHistoryChart";

type PageProps = {
  params:       { id: string };
  searchParams: { sim?: string };
};

export default async function ZonePage({ params, searchParams }: PageProps) {
  const simDate = searchParams.sim ?? null;
  const isSimMode = !!simDate;

  let detail: ZoneDetail | null = null;
  let forecast: Forecast | null = null;

  try {
    if (isSimMode) {
      detail = await fetchSimulationDetail(params.id, simDate!);
    } else {
      [detail, forecast] = await Promise.all([
        fetchDetail(params.id, { cache: "no-store" }),
        fetchForecast(params.id, { cache: "no-store" }),
      ]);
    }
  } catch {}

  if (!detail) return (
    <div style={{ padding: 40, textAlign: "center" }}>
      <div style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 12 }}>Zone introuvable ou backend indisponible.</div>
      <Link href="/" style={{ color: "var(--accent-text)", fontSize: 12 }}>← Retour au tableau de bord</Link>
    </div>
  );

  const backHref = isSimMode ? `/?sim=${simDate}` : "/";

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* Header */}
      <header style={{ background: "var(--bg-card)", borderBottom: "1px solid var(--border)", padding: "12px 24px", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <Link href={backHref} style={{ color: "var(--text-muted)", fontSize: 12 }}>← Toutes les zones</Link>
        <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "0.06em" }}>URBAN SIGNAL ENGINE</span>
        {isSimMode ? (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", padding: "2px 10px", borderRadius: 4 }}>
            SIMULATION · {simDate}
          </span>
        ) : (
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-muted)" }}>
            Live · refresh serveur à chaque requête
          </span>
        )}
      </header>

      {/* Simulation event banner */}
      {isSimMode && detail.sim_events && detail.sim_events.length > 0 && (
        <SimBanner simDate={simDate!} events={detail.sim_events} />
      )}

      <main style={{ maxWidth: 700, margin: "0 auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>

        <ZoneScoreHeader zone={detail} simDate={simDate} />
        <ZoneSignals signals={detail.signals} />

        {!isSimMode && detail.incident_events && (
          <ZoneIncidents events={detail.incident_events} />
        )}

        <ZoneComponentsGrid components={detail.components} />

        {!isSimMode && forecast && (
          <ZoneForecast forecast={forecast} />
        )}

        <ZoneNeighbors neighbors={detail.neighbors} simDate={simDate} />

        {!isSimMode && <ZoneHistoryChart zoneId={detail.zone_id} limit={48} />}

        {isSimMode && (
          <SimBanner simDate={simDate!} zoneId={params.id} />
        )}

      </main>
    </div>
  );
}
