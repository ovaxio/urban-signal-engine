import type { Metadata, Viewport } from "next";
import "./globals.css";
import ThemeProvider from "@/components/theme/ThemeProvider";
import PostHogScript from "@/components/analytics/PostHogScript";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "Urban Signal Engine · Lyon",
  description: "Moteur temps réel de détection de tensions urbaines",
};

/* Anti-FOHT: blocking script sets data-theme before React hydrates */
const ANTI_FOHT = `(function(){try{var t=localStorage.getItem("theme")||"system";var r=t;if(t==="system"){r=window.matchMedia("(prefers-color-scheme:light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",r)}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: ANTI_FOHT }} />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
        <PostHogScript />
      </body>
    </html>
  );
}
