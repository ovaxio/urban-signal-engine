"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
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
    <html lang="fr">
      <body>
        <div style={{ padding: 40, textAlign: "center", fontFamily: "monospace" }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>
            Une erreur est survenue
          </h2>
          <p style={{ fontSize: 12, color: "#888", marginBottom: 16 }}>
            L'erreur a été signalée automatiquement.
          </p>
          <button
            onClick={reset}
            style={{
              fontSize: 12,
              padding: "8px 16px",
              cursor: "pointer",
              background: "var(--bg-control, #222)",
              color: "var(--accent-text, #60a5fa)",
              border: "1px solid var(--border, #333)",
              borderRadius: 4,
            }}
          >
            Réessayer
          </button>
        </div>
      </body>
    </html>
  );
}
