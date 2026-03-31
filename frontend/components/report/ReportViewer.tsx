"use client";

import { useState } from "react";
import type { CalendarEvent, ImpactReport, PreEventReport } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import { fetchEventImpact, fetchImpactReport, fetchPreEventReport } from "@/lib/api";
import ImpactReportView from "./ImpactReportView";
import PreEventReportView from "./PreEventReportView";

type Props = { events: CalendarEvent[] };

export default function ReportViewer({ events }: Props) {
  const [mode, setMode] = useState<"pre-event" | "event" | "custom">("pre-event");

  // Post-event state
  const [report, setReport] = useState<ImpactReport | null>(null);
  // Pre-event state
  const [preReport, setPreReport] = useState<PreEventReport | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom period form
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  // Pre-event date form
  const [preDate, setPreDate] = useState("");

  async function loadPreEventReport(name: string) {
    setLoading(true);
    setError(null);
    try {
      const dateParam = preDate || undefined;
      setPreReport(await fetchPreEventReport(name, dateParam));
      setReport(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
      setPreReport(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadEventReport(name: string) {
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchEventImpact(name));
      setPreReport(null);
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
      setReport(await fetchImpactReport({
        start: `${start}T00:00:00+00:00`,
        end: `${end}T23:59:59+00:00`,
      }));
      setPreReport(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  const tabs: { key: typeof mode; label: string }[] = [
    { key: "pre-event", label: "Pré-événement" },
    { key: "event", label: "Post-événement" },
    { key: "custom", label: "Période libre" },
  ];

  return (
    <>
      {/* Mode selector */}
      <div style={{ display: "flex", gap: 8 }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMode(tab.key)}
            style={{
              padding: "6px 16px",
              fontSize: 12,
              borderRadius: 6,
              border: "1px solid var(--border)",
              background: mode === tab.key ? "var(--accent)" : "var(--bg-card)",
              color: mode === tab.key ? "#fff" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Pre-event: optional date picker */}
      {mode === "pre-event" && (
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
              DATE CIBLE (optionnel — défaut T+48h)
            </span>
            <input
              type="date"
              value={preDate}
              onChange={(e) => setPreDate(e.target.value)}
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
          <div style={{ fontSize: 11, color: "var(--text-muted)", paddingBottom: 6 }}>
            Sélectionnez un événement ci-dessous pour générer le rapport prévisionnel.
          </div>
        </div>
      )}

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

      {/* Loading / Error */}
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

      {/* Reports */}
      {preReport && !loading && <PreEventReportView report={preReport} />}
      {report && !loading && <ImpactReportView report={report} />}

      {/* Event selector — for both pre-event and post-event modes */}
      {(mode === "pre-event" || mode === "event") && (
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
                onClick={() =>
                  mode === "pre-event"
                    ? loadPreEventReport(ev.name)
                    : loadEventReport(ev.name)
                }
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
                  impact {ev.weight}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
