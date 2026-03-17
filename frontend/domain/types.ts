// ── Domain types ────────────────────────────────────────────────────────────

export type ZoneSummary = {
  zone_id: string;
  zone_name: string;
  urban_score: number;
  level: string;
  top_causes: string[];
};

export type ZoneComponents = {
  risk: number;
  anomaly: number;
  conv: number;
  spread: number;
  phi: number;
};

export type ZoneNeighbor = {
  zone_id: string;
  zone_name: string;
  urban_score: number;
  level: string;
};

export type IncidentEvent = {
  type: string;
  label: string;
  detail?: string;
  direction?: string;
  end?: string;
  ends_soon?: boolean;
  weight: number;
  delay_min?: number;
};

export type ZoneDetail = {
  zone_id: string;
  zone_name: string;
  urban_score: number;
  level: string;
  signals: Record<string, number>;
  components: ZoneComponents;
  timestamp: string;
  explanation: string;
  incident_events?: IncidentEvent[];
  neighbors: ZoneNeighbor[];
  sim_events?: string[];
};

export type Alert = {
  ts: string;
  zone_id: string;
  zone_name: string;
  alert_type: "CRITIQUE" | "TENDU" | "CALME";
  urban_score: number;
  prev_score: number;
  level: string;
};

export type ForecastHorizon = {
  horizon: string;
  urban_score: number;
  level: string;
  confidence?: "high" | "medium" | "low";
};

export type Forecast = {
  current_score: number;
  current_level: string;
  forecast: ForecastHorizon[];
  disclaimer: string;
};

export type HealthStatus = {
  cache_age: number;
};

export type HistoryPoint = {
  ts: string;
  urban_score: number;
  traffic: number | null;
  weather: number | null;
  transport: number | null;
  event: number | null;
};

export type FilterLevel = "all" | "TENDU" | "CRITIQUE";

// ── Impact Report ───────────────────────────────────────────────────────────

export type ImpactZone = {
  zone_name: string;
  data_points: number;
  peak_score: number;
  peak_level: string;
  peak_at: string;
  avg_score: number;
  level_distribution: Record<string, number>;
  readings_tendu: number;
  readings_critique: number;
  signal_averages_normalized: Record<string, number>;
  raw_signal_averages: Record<string, number>;
  baseline_avg_score: number | null;
  delta_vs_baseline: number | null;
};

export type ImpactSummary = {
  total_data_points: number;
  zones_analyzed: number;
  global_avg_score: number;
  global_peak_score: number;
  global_peak_zone: string;
  global_peak_at: string;
  global_peak_level: string;
  baseline_avg_score: number | null;
  delta_vs_baseline: number | null;
  total_alerts: number;
  alerts_critique: number;
  alerts_tendu: number;
};

export type ImpactTopZone = {
  zone_id: string;
  zone_name: string;
  avg_score: number;
  peak_score: number;
  peak_level: string;
};

export type ImpactReport = {
  report_type: string;
  event_name: string | null;
  period: { start: string; end: string };
  baseline_period: { start: string; end: string } | null;
  summary: ImpactSummary;
  top_impacted_zones: ImpactTopZone[];
  zones: Record<string, ImpactZone>;
  alerts: Alert[];
};

export type CalendarEvent = {
  name: string;
  start: string;
  end: string;
  zone: string;
  zone_name: string;
  weight: number;
};

// ── Forecast Accuracy ──────────────────────────────────────────────────────

export type ForecastAccuracyHorizon = {
  horizon: string;
  n: number;
  mae: number | null;
  mae_clean: number | null;
  n_surprise: number;
  bias: number | null;
  min_delta: number | null;
  max_delta: number | null;
};

export type ForecastEvaluation = {
  ts_forecast: string;
  zone_id: string;
  horizon: string;
  predicted_score: number;
  actual_score: number;
  delta: number;
  incident_surprise: number;
  evaluated_at: string;
};

export type ForecastAccuracy = {
  total_evaluated: number;
  mae_global: number | null;
  incident_surprises: number;
  by_horizon: ForecastAccuracyHorizon[];
  recent: ForecastEvaluation[];
};
