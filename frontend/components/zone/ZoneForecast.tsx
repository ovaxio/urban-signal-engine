"use client";

import type { Forecast } from "@/domain/types";
import { scoreColor } from "@/domain/scoring";
import { useCountUp } from "@/hooks/useCountUp";

type Props = {
  forecast: Forecast;
};

function ForecastScore({ value }: { value: number }) {
  const display = useCountUp(value, 800);
  return <>{display}</>;
}

export default function ZoneForecast({ forecast }: Props) {
  return (
    <div style={{ background: "var(--bg-card)", borderRadius: 12, padding: 20, border: "1px solid var(--border)" }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", marginBottom: 14, fontWeight: 600 }}>PRÉVISION</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))", gap: 10 }}>
        <div style={{ textAlign: "center", padding: 14, background: "var(--bg-inner)", borderRadius: 8, border: `1px solid ${scoreColor(forecast.current_score)}44` }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 5 }}>Maintenant</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(forecast.current_score) }}><ForecastScore value={forecast.current_score} /></div>
          <div style={{ fontSize: 10, color: scoreColor(forecast.current_score), marginTop: 3 }}>{forecast.current_level}</div>
        </div>
        {forecast.forecast.map(f => (
          <div key={f.horizon} style={{ textAlign: "center", padding: 14, background: "var(--bg-inner)", borderRadius: 8, border: `1px solid ${scoreColor(f.urban_score)}33` }}>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 5 }}>+{f.horizon}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: scoreColor(f.urban_score), opacity: f.confidence === "low" ? 0.6 : 1 }}><ForecastScore value={f.urban_score} /></div>
            <div style={{ fontSize: 10, color: scoreColor(f.urban_score), marginTop: 3 }}>{f.level}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 8 }}>{forecast.disclaimer}</div>
    </div>
  );
}
