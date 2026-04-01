import os
from typing import Any, Dict, List

EPSILON: float = 0.001

WEIGHTS: Dict[str, float] = {
    "traffic":   0.35,
    "incident":  0.25,
    "transport": 0.15,
    "weather":   0.15,
    "event":     0.10,
}

LAMBDA: Dict[str, float] = {
    "l1": 1.0,
    "l2": 1.0,
    "l3": 0.6,
    "l4": 0.4,
}

THETA: Dict[str, float] = {
    "traffic":   1.5,
    "weather":   1.2,
    "event":     1.0,
    "transport": 1.5,
    "incident":  1.0,  # ← seuil convergence incidents
}

ALPHA: Dict[str, float] = {
    "traffic":   0.30,
    "weather":   0.10,
    "event":     0.05,
    "transport": 0.25,
    "incident":  0.30,  # ← nouveau signal
}

BETA: Dict[str, float] = {
    "traffic_weather":    0.3,
    "traffic_event":      0.2,
    "traffic_transport":  0.4,
    "traffic_incident":   0.6,  # ← convergence trafic + incidents = fort signal
    "weather_event":      0.2,
    "weather_transport":  0.2,
    "weather_incident":   0.3,
    "event_transport":    0.3,
    "event_incident":     0.3,
    "transport_incident": 0.4,
}

# Borne max de Σβ_k — validation au démarrage, ValueError si dépassée.
# Σβ_k actuel = 3.20. Valeur par défaut à 3.5 pour garder une marge.
# Réduire B si on réduit les β, ou augmenter si on ajoute des paires.
CONV_BETA_SUM_MAX: float = 3.5

# Seuil max acceptable pour sigmoid(0 − θ) à z=0 (régime neutre).
# Si dépassé : warning au boot (conv a un fond résiduel non négligeable).
CONV_THETA_EPSILON: float = 0.05

SPATIAL_KERNEL_DECAY: float = 0.6
# Horizons courts (temps réel) + étendus (structurels)
FORECAST_HORIZONS: List[int] = [30, 60, 120]
FORECAST_HORIZONS_EXTENDED: List[int] = [360, 720, 1440]  # 6h, 12h, 24h
INCIDENT_FORECAST_HALFLIFE_MIN: int = 240  # 4h — decay incidents dans forecast étendu (ADR-013)
# Criter : 2 appels/refresh (trafic + incidents), sans quota → TTL 60s
CACHE_TTL_SECONDS: int = 60
ENABLE_HISTORY: bool = os.getenv("ENABLE_HISTORY", "true").lower() == "true"

# ── Seuils météo Open-Meteo ──────────────────────────────────────────────────
# Utilisés par ingestion._weather_score_from_values() pour convertir les
# données brutes Open-Meteo en score météo synthétique [0, 3.0].
WEATHER_PRECIP_DIVISOR: float = 5.0    # mm → score : score += min(precip / divisor, 1.5)
WEATHER_WIND_THRESHOLD: float = 50.0   # km/h — au-delà → +0.5
WEATHER_SCORE_MAX: float = 3.0         # borne haute du score météo

# Lookup granulaire WMO → contribution score (ADR-017)
# Capte la perturbation opérationnelle (mobilité/trafic), pas le risque criminologique.
# Codes source : https://open-meteo.com/en/docs/weather_code
WEATHER_WMO_SCORE: Dict[int, float] = {
    0: 0.0,   # Clear sky
    1: 0.0,   # Mainly clear
    2: 0.0,   # Partly cloudy
    3: 0.0,   # Overcast
    45: 0.4,  # Fog
    48: 0.4,  # Depositing rime fog
    51: 0.2,  # Drizzle light
    53: 0.2,  # Drizzle moderate
    55: 0.2,  # Drizzle dense
    61: 0.3,  # Rain slight
    63: 0.5,  # Rain moderate
    65: 0.8,  # Rain heavy
    71: 0.7,  # Snow fall slight
    73: 0.7,  # Snow fall moderate
    75: 0.7,  # Snow fall heavy
    77: 0.7,  # Snow grains
    80: 0.2,  # Rain showers slight
    81: 0.5,  # Rain showers moderate
    82: 1.0,  # Rain showers violent
    85: 0.7,  # Snow showers slight
    86: 0.7,  # Snow showers heavy
    95: 1.5,  # Thunderstorm slight/moderate
    96: 1.5,  # Thunderstorm with slight hail
    99: 1.5,  # Thunderstorm with heavy hail
}

# ── Auto-apprentissage forecast (ADR-018) ─────────────────────────────────────
FORECAST_LEARN_DEFAULTS: Dict[str, Any] = {
    "scenario_weights": {"persist": 0.25, "maintained": 0.55, "proj": 0.20},
    "scenario_weights_no_proj": {"persist": 0.30, "maintained": 0.70},
    "decay_halflife_min": 240,
    "incident_halflife_min": 240,
}
FORECAST_LEARN_BOUNDS: Dict[str, tuple] = {
    "weight_min": 0.10,
    "weight_max": 0.80,
    "halflife_min": 120,
    "halflife_max": 480,
}
FORECAST_LEARN_MIN_N: int = 100       # min evaluations per horizon before learning
FORECAST_LEARN_ALPHA: float = 0.15    # EMA smoothing factor (~6 weeks memory)
FORECAST_LEARN_MAX_STEP: float = 0.05 # max weight change per cycle

# ── Multi-zone contribution gaussienne (ADR-019) ─────────────────────────────
# Chaque point (segment trafic, incident, station) contribue à plusieurs zones
# avec poids gaussien décroissant. Désactivé par défaut (nearest-centroid legacy).
MULTIZONE_ENABLED: bool = os.getenv("MULTIZONE_ENABLED", "false").lower() == "true"
MULTIZONE_SIGMA_KM: float = 1.2   # sigma gaussien — à 0.8km: w≈0.72, 1.2km: w≈0.61, 2km: w≈0.19
MULTIZONE_MIN_WEIGHT: float = 0.05  # ignore contributions < 5% (bruit zones lointaines)

# Mapping état Criter → ratio synthétique de congestion
# V=fluide, O=dense, R=chargé, N=coupée, G/*/inconnu=ignoré
CRITER_ETAT_TO_RATIO: Dict[str, float] = {
    "V": 1.0,   # vert  = fluide  — circulation normale
    "O": 2.0,   # orange= dense   — ralentissements
    "R": 2.8,   # rouge = chargé  — embouteillages
    "N": 3.0,   # noir  = coupée  — route fermée
}


class ExternalAPIs:
    WEATHER_URL = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=45.748&longitude=4.847"
        "&current=precipitation,wind_speed_10m,temperature_2m,weather_code"
        "&timezone=Europe/Paris"
    )
    # Open-Meteo forecast horaire (precipitation, vent, weather_code sur 48h)
    WEATHER_FORECAST_URL = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=45.748&longitude=4.847"
        "&hourly=precipitation,wind_speed_10m,weather_code"
        "&timezone=Europe/Paris"
        "&forecast_days=2"
    )
    TCL_GTFS_RT_URL       = "https://data.sytral.fr/gtfs-rt/vehicle_positions"
    TCL_DISRUPTIONS_URL   = "https://data.sytral.fr/api/disruptions"
    OVERPASS_URL          = "https://overpass-api.de/api/interpreter"
    # Criter — trafic temps réel Métropole de Lyon (Grand Lyon open data, sans quota)
    CRITER_WFS_URL        = (
        "https://download.data.grandlyon.com/wfs/grandlyon"
        "?SERVICE=WFS&VERSION=2.0.0&request=GetFeature"
        "&typename=pvo_patrimoine_voirie.pvotrafic"
        "&SRSNAME=EPSG:4326&outputFormat=application/json&count=2000"
        "&BBOX=4.77,45.70,4.93,45.82,EPSG:4326"
    )
    # Criter — événements perturbateurs (incidents, travaux, manifs)
    CRITER_EVENTS_URL     = (
        "https://download.data.grandlyon.com/wfs/grandlyon"
        "?SERVICE=WFS&VERSION=2.0.0&request=GetFeature"
        "&typename=pvo_patrimoine_voirie.pvoevenement"
        "&SRSNAME=EPSG:4326&outputFormat=application/json&count=500"
        "&BBOX=4.77,45.70,4.93,45.82,EPSG:4326"
    )

APIS = ExternalAPIs()

# ── Centroïdes des 12 zones lyonnaises ────────────────────────────────────────
# Source unique — utilisé par ingestion (nearest_zone) et events (haversine).
# SYNC: frontend/domain/constants.ts doit refléter ces valeurs exactement.
ZONE_CENTROIDS = {
    "part-dieu":    (45.7580, 4.8490),
    "presquile":    (45.7558, 4.8320),
    "vieux-lyon":   (45.7622, 4.8271),
    "perrache":     (45.7488, 4.8286),
    "gerland":      (45.7283, 4.8336),
    "guillotiere":  (45.7460, 4.8430),
    "brotteaux":    (45.7690, 4.8560),
    "villette":     (45.7720, 4.8620),
    "montchat":     (45.7560, 4.8760),
    "fourviere":    (45.7622, 4.8150),
    "croix-rousse": (45.7760, 4.8320),
    "confluence":   (45.7400, 4.8200),
}