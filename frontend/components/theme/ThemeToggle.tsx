"use client";

import { useTheme, type ThemeChoice } from "./ThemeProvider";

const CYCLE: ThemeChoice[] = ["dark", "light", "system"];
const ICONS: Record<ThemeChoice, string> = { dark: "☾", light: "☀", system: "◑" };
const LABELS: Record<ThemeChoice, string> = { dark: "Thème sombre", light: "Thème clair", system: "Thème système" };

export default function ThemeToggle() {
  const { choice, mounted, setTheme } = useTheme();

  const next = () => {
    const idx = CYCLE.indexOf(choice);
    setTheme(CYCLE[(idx + 1) % CYCLE.length]);
  };

  return (
    <button
      onClick={next}
      aria-label={mounted ? LABELS[choice] : LABELS.system}
      title={mounted ? LABELS[choice] : LABELS.system}
      style={{
        fontSize: 14,
        color: "var(--text-secondary)",
        background: "var(--bg-control)",
        border: "1px solid var(--border)",
        borderRadius: 4,
        padding: "4px 10px",
        cursor: "pointer",
        minHeight: 36,
        minWidth: 36,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
      }}
    >
      <span aria-hidden="true">{mounted ? ICONS[choice] : ICONS.system}</span>
    </button>
  );
}
