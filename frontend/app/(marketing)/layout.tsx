import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Urban Signal Engine — Anticipez les tensions urbaines à Lyon",
  description:
    "Recevez un rapport d'anticipation 48h avant votre événement. " +
    "Score de tension urbaine en temps réel sur 12 zones lyonnaises.",
  openGraph: {
    title: "Urban Signal Engine — Rapport d'anticipation événement",
    description:
      "Score de tension urbaine temps réel à Lyon. " +
      "Rapport PDF 390€ HT par événement.",
    locale: "fr_FR",
    type: "website",
  },
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
