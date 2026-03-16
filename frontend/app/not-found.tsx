import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{ padding: 40, textAlign: "center" }}>
      <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Page introuvable</h2>
      <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 16 }}>
        La page demandée n'existe pas.
      </p>
      <Link href="/" style={{ color: "var(--accent-text)", fontSize: 12 }}>
        ← Retour à l&apos;accueil
      </Link>
    </div>
  );
}
