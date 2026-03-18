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
    <div className="p-10 text-center font-mono">
      <h2 className="mb-2 text-base font-bold text-text-primary">
        Erreur sur la page zone
      </h2>
      <p className="mb-4 text-xs text-text-secondary">
        L&apos;erreur a été signalée automatiquement.
      </p>
      <div className="flex justify-center gap-3">
        <button
          onClick={reset}
          className="cursor-pointer rounded border border-border bg-bg-control px-4 py-2 text-xs text-accent-text"
        >
          Réessayer
        </button>
        <Link href="/dashboard" className="px-4 py-2 text-xs text-text-secondary">
          ← Tableau de bord
        </Link>
      </div>
    </div>
  );
}
