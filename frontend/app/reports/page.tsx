import { fetchEvents } from "@/lib/api";
import type { CalendarEvent } from "@/domain/types";
import AppNav from "@/components/layout/AppNav";
import ReportViewer from "@/components/report/ReportViewer";

export const metadata = {
  title: "Rapports d'impact — Urban Signal Engine",
  description: "Analyse post-événement de l'impact sur les zones urbaines de Lyon.",
};

export default async function ReportsPage() {
  let events: CalendarEvent[] = [];
  try {
    const data = await fetchEvents();
    events = data.events ?? [];
  } catch {}

  return (
    <div style={{ minHeight: "100vh" }}>
      <header
        style={{
          background: "var(--bg-card)",
          borderBottom: "1px solid var(--border)",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "0.06em" }}>
          URBAN SIGNAL ENGINE
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          RAPPORTS D&apos;IMPACT
        </span>
      </header>
      <AppNav />

      <main
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 24,
        }}
      >
        <ReportViewer events={events} />
      </main>
    </div>
  );
}
