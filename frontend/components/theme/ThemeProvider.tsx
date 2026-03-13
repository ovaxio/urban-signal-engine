"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";

export type ThemeChoice = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

type ThemeCtx = {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
  mounted: boolean;
  setTheme: (t: ThemeChoice) => void;
};

const ThemeContext = createContext<ThemeCtx>({
  choice: "system",
  resolved: "dark",
  mounted: false,
  setTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function resolve(choice: ThemeChoice): ResolvedTheme {
  return choice === "system" ? getSystemTheme() : choice;
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [choice, setChoice] = useState<ThemeChoice>("system");
  const [resolved, setResolved] = useState<ResolvedTheme>("dark");
  const [mounted, setMounted] = useState(false);

  const applyTheme = useCallback((c: ThemeChoice) => {
    const r = resolve(c);
    document.documentElement.setAttribute("data-theme", r);
    setResolved(r);
  }, []);

  // Hydrate from localStorage after mount
  useEffect(() => {
    const stored = (localStorage.getItem("theme") as ThemeChoice) ?? "system";
    setChoice(stored);
    applyTheme(stored);
    setMounted(true);
  }, [applyTheme]);

  // Apply on choice change + persist (skip until mounted)
  useEffect(() => {
    if (!mounted) return;
    localStorage.setItem("theme", choice);
    applyTheme(choice);
  }, [choice, applyTheme, mounted]);

  // Listen for OS preference changes when in system mode
  useEffect(() => {
    if (choice !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [choice, applyTheme]);

  return (
    <ThemeContext.Provider value={{ choice, resolved, mounted, setTheme: setChoice }}>
      {children}
    </ThemeContext.Provider>
  );
}
