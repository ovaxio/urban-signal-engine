"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import Link from "next/link";

export default function ZoneDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div style={{ padding: 40, textAlign: "center", fontFamily: "monospace" }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: "var(--text-primary)" }}>
        Erreur sur la page zone
      </h2>
      <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 16 }}>
        L&apos;erreur a été signalée automatiquement.
      </p>
      <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
        <button
          onClick={reset}
          style={{
            fontSize: 12,
            padding: "8px 16px",
            cursor: "pointer",
            background: "var(--bg-control)",
            color: "var(--accent-text)",
            border: "1px solid var(--border)",
            borderRadius: 4,
          }}
        >
          Réessayer
        </button>
        <Link
          href="/dashboard"
          style={{ fontSize: 12, padding: "8px 16px", color: "var(--text-secondary)" }}
        >
          ← Tableau de bord
        </Link>
      </div>
    </div>
  );
}
