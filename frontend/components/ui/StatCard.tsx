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

export default function StatCard({ label, value, color = "#64748b" }: Props) {
  return (
    <div style={{ background: "#1a1d27", border: "1px solid #2d3148", borderRadius: 8, padding: "10px 16px", flex: 1, minWidth: 120 }}>
      <div style={{ fontSize: 9, color: "#94a3b8", letterSpacing: "0.08em", marginBottom: 4 }}>{label.toUpperCase()}</div>
      {typeof value === "number"
        ? <AnimatedNumber value={value} color={color} />
        : <div style={{ fontSize: 20, fontWeight: 700, color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
      }
    </div>
  );
}
