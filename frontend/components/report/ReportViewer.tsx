"use client";

import { useState } from "react";
import type { CalendarEvent, ImpactReport } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import ImpactReportView from "./ImpactReportView";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Props = { events: CalendarEvent[] };

export default function ReportViewer({ events }: Props) {
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"event" | "custom">("event");

  // Custom period form
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  async function loadEventReport(name: string) {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(
        `${BASE}/reports/impact/event/${encodeURIComponent(name)}`,
        { cache: "no-store" }
      );
      if (!r.ok) {
        const body = await r.json().catch(() => null);
        throw new Error(body?.detail ?? `Erreur ${r.status}`);
      }
      setReport(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadCustomReport() {
    if (!start || !end) return;
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams({
        start: `${start}T00:00:00+00:00`,
        end: `${end}T23:59:59+00:00`,
      });
      const r = await fetch(`${BASE}/reports/impact?${q}`, { cache: "no-store" });
      if (!r.ok) {
        const body = await r.json().catch(() => null);
        throw new Error(body?.detail ?? `Erreur ${r.status}`);
      }
      setReport(await r.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Mode selector */}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => setMode("event")}
          style={{
            padding: "6px 16px",
            fontSize: 12,
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: mode === "event" ? "var(--accent)" : "var(--bg-card)",
            color: mode === "event" ? "#fff" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          Par événement
        </button>
        <button
          onClick={() => setMode("custom")}
          style={{
            padding: "6px 16px",
            fontSize: 12,
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: mode === "custom" ? "var(--accent)" : "var(--bg-card)",
            color: mode === "custom" ? "#fff" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          Période libre
        </button>
      </div>

      {/* Custom period form */}
      {mode === "custom" && (
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 16,
            display: "flex",
            gap: 12,
            alignItems: "flex-end",
            flexWrap: "wrap",
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            <span style={{ color: "var(--text-secondary)", fontSize: 10, letterSpacing: "0.06em" }}>
              DÉBUT
            </span>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--bg-inner)",
                color: "var(--text-primary)",
                fontSize: 12,
              }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            <span style={{ color: "var(--text-secondary)", fontSize: 10, letterSpacing: "0.06em" }}>
              FIN
            </span>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--bg-inner)",
                color: "var(--text-primary)",
                fontSize: 12,
              }}
            />
          </label>
          <button
            onClick={loadCustomReport}
            disabled={loading || !start || !end}
            style={{
              padding: "6px 20px",
              borderRadius: 6,
              border: "none",
              background: "var(--accent)",
              color: "#fff",
              fontSize: 12,
              fontWeight: 600,
              cursor: loading ? "wait" : "pointer",
              opacity: !start || !end ? 0.5 : 1,
            }}
          >
            Générer
          </button>
        </div>
      )}

      {/* Loading / Error — au-dessus du contenu pour visibilité immédiate */}
      {loading && (
        <div
          style={{
            padding: 24,
            textAlign: "center",
            color: "var(--text-muted)",
            fontSize: 13,
          }}
        >
          Analyse en cours...
        </div>
      )}
      {error && !loading && (
        <div
          style={{
            padding: 16,
            borderRadius: 8,
            background: "#ef44441a",
            border: "1px solid #ef444433",
            color: "#ef4444",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Report */}
      {report && !loading && <ImpactReportView report={report} />}

      {/* Event selector — en bas, après le résultat */}
      {mode === "event" && (
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: "var(--text-secondary)",
              letterSpacing: "0.06em",
              marginBottom: 12,
            }}
          >
            CALENDRIER DES ÉVÉNEMENTS LYON 2026
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {events.map((ev) => (
              <button
                key={ev.name}
                onClick={() => loadEventReport(ev.name)}
                disabled={loading}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "var(--bg-inner)",
                  cursor: loading ? "wait" : "pointer",
                  textAlign: "left",
                  transition: "border-color 0.15s",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                    {ev.name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                    {ev.zone_name} · {ev.start} → {ev.end}
                  </div>
                </div>
                <div
                  style={{
                    fontSize: 10,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "var(--bg-control)",
                    color: "var(--text-secondary)",
                  }}
                >
                  poids {ev.weight}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
