import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-page":      "var(--bg-page)",
        "bg-card":      "var(--bg-card)",
        "bg-inner":     "var(--bg-inner)",
        "bg-control":   "var(--bg-control)",
        border:         "var(--border)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted":   "var(--text-muted)",
        "text-faint":   "var(--text-faint)",
        accent:         "var(--accent)",
        "accent-text":  "var(--accent-text)",
      },
    },
  },
  plugins: [],
};

export default config;
