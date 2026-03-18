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
      className="flex min-h-9 min-w-9 cursor-pointer items-center justify-center gap-1 rounded border border-border bg-bg-control px-2.5 py-1 text-sm text-text-secondary"
    >
      <span aria-hidden="true">{mounted ? ICONS[choice] : ICONS.system}</span>
    </button>
  );
}
