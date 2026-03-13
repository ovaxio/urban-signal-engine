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
  horizon_min: number;
  urban_score: number;
  level: string;
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
