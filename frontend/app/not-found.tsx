import Link from "next/link";

export default function NotFound() {
  return (
    <div className="p-10 text-center">
      <h2 className="mb-2 text-base font-bold">Page introuvable</h2>
      <p className="mb-4 text-xs text-text-secondary">
        La page demandée n&apos;existe pas.
      </p>
      <Link href="/" className="text-xs text-accent-text">
        ← Retour à l&apos;accueil
      </Link>
    </div>
  );
}
