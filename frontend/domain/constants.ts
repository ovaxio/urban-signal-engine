// ── Labels, icons, weights — single source of truth ─────────────────────────

export const SIGNAL_LABELS: Record<string, string> = {
  traffic:   "Trafic",
  weather:   "Météo",
  event:     "Événement",
  transport: "Transport TCL",
  incident:  "Incidents",
};

export const EVENT_ICONS: Record<string, string> = {
  roadClosed:        "🚧",
  march:             "✊",
  demonstration:     "✊",
  publicEvent:       "🎭",
  sportEvent:        "🏟️",
  other:             "⚠️",
  Activities:        "🎭",
  NetworkManagement: "🚧",
  AbnormalTraffic:   "🚦",
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  roadClosed:        "Fermeture",
  march:             "Manifestation",
  demonstration:     "Manifestation",
  publicEvent:       "Événement",
  sportEvent:        "Sport",
  other:             "Divers",
  Activities:        "Activité",
  NetworkManagement: "Réseau",
  AbnormalTraffic:   "Trafic anormal",
};

// Source: backend/config.py ZONE_CENTROIDS — ne pas modifier ici, modifier config.py.
export const ZONE_CENTROIDS: Record<string, [number, number]> = {
  "part-dieu":    [45.7580, 4.8490],
  "presquile":    [45.7558, 4.8320],
  "vieux-lyon":   [45.7622, 4.8271],
  "perrache":     [45.7488, 4.8286],
  "gerland":      [45.7283, 4.8336],
  "guillotiere":  [45.7460, 4.8430],
  "brotteaux":    [45.7690, 4.8560],
  "villette":     [45.7720, 4.8620],
  "montchat":     [45.7560, 4.8760],
  "fourviere":    [45.7622, 4.8150],
  "croix-rousse": [45.7760, 4.8320],
  "confluence":   [45.7400, 4.8200],
};

export const COMPONENT_KEYS = ["risk", "anomaly", "conv", "spread", "phi"] as const;

export const REFRESH_INTERVAL = 30_000;
