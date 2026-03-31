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
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="mb-3.5 text-[10px] font-semibold tracking-widest text-text-muted">PRÉVISION D'ÉVOLUTION</div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(80px,1fr))] gap-2.5">
        <div className="rounded-lg bg-bg-inner p-3.5 text-center" style={{ border: `1px solid ${scoreColor(forecast.current_score)}44` }}>
          <div className="mb-1.5 text-[10px] text-text-muted">Maintenant</div>
          <div className="text-[28px] font-bold" style={{ color: scoreColor(forecast.current_score) }}><ForecastScore value={forecast.current_score} /></div>
          <div className="mt-0.5 text-[10px]" style={{ color: scoreColor(forecast.current_score) }}>{forecast.current_level}</div>
        </div>
        {forecast.forecast.map(f => (
          <div key={f.horizon} className="rounded-lg bg-bg-inner p-3.5 text-center" style={{ border: `1px solid ${scoreColor(f.urban_score)}33` }}>
            <div className="mb-1.5 text-[10px] text-text-muted">+{f.horizon}</div>
            <div className="text-[28px] font-bold" style={{ color: scoreColor(f.urban_score), opacity: f.confidence === "low" ? 0.6 : 1 }}><ForecastScore value={f.urban_score} /></div>
            <div className="mt-0.5 text-[10px]" style={{ color: scoreColor(f.urban_score) }}>{f.level}</div>
          </div>
        ))}
      </div>
      <div className="mt-2 text-[10px] text-text-muted">{forecast.disclaimer}</div>
    </div>
  );
}
