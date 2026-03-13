import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Urban Signal Engine · Lyon",
  description: "Moteur temps réel de détection de tensions urbaines",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
