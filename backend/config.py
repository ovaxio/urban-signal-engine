import os
from typing import Dict, List

EPSILON: float = 0.001

WEIGHTS: Dict[str, float] = {
    "traffic":   0.30,
    "weather":   0.10,
    "event":     0.05,
    "transport": 0.25,
    "incident":  0.30,  # ← nouveau signal
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
FORECAST_HORIZONS: List[int] = [30, 60, 120]
# Criter : 2 appels/refresh (trafic + incidents), sans quota → TTL 60s
CACHE_TTL_SECONDS: int = 60
ENABLE_HISTORY: bool = os.getenv("ENABLE_HISTORY", "true").lower() == "true"

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