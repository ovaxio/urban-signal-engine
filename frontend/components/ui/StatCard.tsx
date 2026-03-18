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
    <div className="text-xl font-bold" style={{ color }}>{display}</div>
  );
}

export default function StatCard({ label, value, color = "var(--text-muted)" }: Props) {
  return (
    <div className="min-w-[120px] flex-1 rounded-lg border border-border bg-bg-card px-4 py-2.5">
      <div className="mb-1 text-[9px] tracking-wider text-text-secondary">{label.toUpperCase()}</div>
      {typeof value === "number"
        ? <AnimatedNumber value={value} color={color} />
        : <div className="truncate text-xl font-bold" style={{ color }}>{value}</div>
      }
    </div>
  );
}
