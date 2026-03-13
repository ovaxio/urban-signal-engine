"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";

export type ThemeChoice = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

type ThemeCtx = {
  choice: ThemeChoice;
  resolved: ResolvedTheme;
  setTheme: (t: ThemeChoice) => void;
};

const ThemeContext = createContext<ThemeCtx>({
  choice: "system",
  resolved: "dark",
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
  const [choice, setChoice] = useState<ThemeChoice>(() => {
    if (typeof window === "undefined") return "system";
    return (localStorage.getItem("theme") as ThemeChoice) ?? "system";
  });

  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolve(choice));

  const applyTheme = useCallback((c: ThemeChoice) => {
    const r = resolve(c);
    document.documentElement.setAttribute("data-theme", r);
    setResolved(r);
  }, []);

  // Apply on choice change + persist
  useEffect(() => {
    localStorage.setItem("theme", choice);
    applyTheme(choice);
  }, [choice, applyTheme]);

  // Listen for OS preference changes when in system mode
  useEffect(() => {
    if (choice !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [choice, applyTheme]);

  return (
    <ThemeContext.Provider value={{ choice, resolved, setTheme: setChoice }}>
      {children}
    </ThemeContext.Provider>
  );
}
