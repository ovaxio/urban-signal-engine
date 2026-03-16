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
import AppHeader          from "@/components/layout/AppHeader";
import AppNav             from "@/components/layout/AppNav";
import ZoneHistoryChart   from "@/components/chart/ZoneHistoryChart";

type PageProps = {
  params:       Promise<{ id: string }>;
  searchParams: Promise<{ sim?: string }>;
};

export default async function ZonePage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const { sim } = await searchParams;
  const simDate = sim ?? null;
  const isSimMode = !!simDate;

  let detail: ZoneDetail | null = null;
  let forecast: Forecast | null = null;

  try {
    if (isSimMode) {
      detail = await fetchSimulationDetail(id, simDate!);
    } else {
      [detail, forecast] = await Promise.all([
        fetchDetail(id, { cache: "no-store" }),
        fetchForecast(id, { cache: "no-store" }),
      ]);
    }
  } catch {}

  if (!detail) return (
    <div style={{ padding: 40, textAlign: "center" }}>
      <div style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 12 }}>Zone introuvable ou backend indisponible.</div>
      <Link href="/dashboard" style={{ color: "var(--accent-text)", fontSize: 12 }}>← Retour au tableau de bord</Link>
    </div>
  );

  const backHref = isSimMode ? `/dashboard?sim=${simDate}` : "/dashboard";

  return (
    <div style={{ minHeight: "100vh" }}>

      {/* Header */}
      <AppHeader
        back={{ href: backHref, text: "Toutes les zones" }}
        right={
          isSimMode ? (
            <span style={{ fontSize: 11, color: "#f97316", background: "#f9731611", border: "1px solid #f9731633", padding: "2px 10px", borderRadius: 4 }}>
              SIMULATION · {simDate}
            </span>
          ) : (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Live
            </span>
          )
        }
      />
      <AppNav />

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
          <SimBanner simDate={simDate!} zoneId={id} />
        )}

      </main>
    </div>
  );
}
