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

export const ZONE_CENTROIDS: Record<string, [number, number]> = {
  "part-dieu":    [45.7605, 4.8597],
  "presquile":    [45.7640, 4.8330],
  "vieux-lyon":   [45.7620, 4.8270],
  "perrache":     [45.7490, 4.8280],
  "gerland":      [45.7330, 4.8330],
  "guillotiere":  [45.7530, 4.8450],
  "brotteaux":    [45.7650, 4.8680],
  "villette":     [45.7580, 4.8780],
  "montchat":     [45.7540, 4.8900],
  "fourviere":    [45.7620, 4.8200],
  "croix-rousse": [45.7780, 4.8370],
  "confluence":   [45.7430, 4.8210],
};

export const COMPONENT_KEYS = ["risk", "anomaly", "conv", "spread", "phi"] as const;

export const REFRESH_INTERVAL = 30_000;
