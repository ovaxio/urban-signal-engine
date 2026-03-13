import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Urban Signal Engine · Détection prédictive des tensions urbaines · Lyon",
  description:
    "Plateforme temps réel qui agrège trafic, météo, transports et événements pour anticiper les crises urbaines sur la métropole de Lyon.",
  openGraph: {
    title: "Urban Signal Engine · Lyon",
    description:
      "Score prédictif par quartier — détectez les tensions urbaines avant qu'elles n'éclatent.",
    type: "website",
  },
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
