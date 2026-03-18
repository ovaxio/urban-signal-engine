import os
from typing import Dict, List

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
# Criter : 2 appels/refresh (trafic + incidents), sans quota → TTL 60s
CACHE_TTL_SECONDS: int = 60
ENABLE_HISTORY: bool = os.getenv("ENABLE_HISTORY", "true").lower() == "true"

# ── Seuils météo Open-Meteo ──────────────────────────────────────────────────
# Utilisés par ingestion._weather_score_from_values() pour convertir les
# données brutes Open-Meteo en score météo synthétique [0, 3.0].
WEATHER_PRECIP_DIVISOR: float = 5.0    # mm → score : score += min(precip / divisor, 1.5)
WEATHER_WIND_THRESHOLD: float = 50.0   # km/h — au-delà → +0.5
WEATHER_WMO_SEVERE: int = 95           # code WMO ≥ 95 (orage violent) → +1.5
WEATHER_WMO_MODERATE: int = 61         # code WMO ≥ 61 (pluie modérée) → +0.8
WEATHER_SCORE_MAX: float = 3.0         # borne haute du score météo

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
    "fourviere":    (45.7622, 4.8200),
    "croix-rousse": (45.7760, 4.8320),
    "confluence":   (45.7380, 4.8170),
}