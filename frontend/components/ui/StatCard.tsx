"use client";

import { useCountUp } from "@/hooks/useCountUp";

type Props = {
  label: string;
  value: string | number;
  color?: string;
};

function AnimatedNumber({ value, color }: { value: number; color: string }) {
  const display = useCountUp(value);
  return (
    <div style={{ fontSize: 20, fontWeight: 700, color }}>{display}</div>
  );
}

export default function StatCard({ label, value, color = "var(--text-muted)" }: Props) {
  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9, color: "var(--text-secondary)", letterSpacing: "0.08em", marginBottom: 4 }}>{label.toUpperCase()}</div>
      {typeof value === "number"
        ? <AnimatedNumber value={value} color={color} />
        : <div style={{ fontSize: 20, fontWeight: 700, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
      }
    </div>
  );
}
