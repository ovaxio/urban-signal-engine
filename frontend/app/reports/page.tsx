import { fetchEvents } from "@/lib/api";
import type { CalendarEvent } from "@/domain/types";
import AppHeader from "@/components/layout/AppHeader";
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
      <AppHeader label="RAPPORTS D'IMPACT" />
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
