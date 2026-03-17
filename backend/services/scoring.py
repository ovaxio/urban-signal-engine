import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from zoneinfo import ZoneInfo

LYON_TZ = ZoneInfo("Europe/Paris")

from config import EPSILON, WEIGHTS, LAMBDA, THETA, ALPHA, BETA, SPATIAL_KERNEL_DECAY, FORECAST_HORIZONS

BASELINE = {
    "traffic":   {"mu": 1.30, "sigma": 0.50},   # Criter : V=1.0 O=2.0 R=2.8 N=3.0
    "weather":   {"mu": 0.3,  "sigma": 0.35},
    "event":     {"mu": 0.2,  "sigma": 0.3},
    "transport": {"mu": 0.45, "sigma": 0.35},
    "incident":  {"mu": 0.8,  "sigma": 0.6},
}

# Baselines par zone — surchargent BASELINE si disponibles (calibrées depuis SQLite)
# Structure : zone_id → signal → {mu, sigma}
ZONE_BASELINES: Dict[str, Dict[str, Dict[str, float]]] = {}


def _effective_baseline(zone_id: str) -> Dict[str, Dict[str, float]]:
    """Retourne le baseline effectif pour une zone : zone-specific si dispo, global sinon."""
    zone_bl = ZONE_BASELINES.get(zone_id, {})
    if not zone_bl:
        return BASELINE
    return {sig: zone_bl.get(sig, BASELINE[sig]) for sig in BASELINE}

NEIGHBORS = {
    "part-dieu":    ["brotteaux","villette","montchat","guillotiere"],
    "presquile":    ["part-dieu","vieux-lyon","perrache","guillotiere"],
    "vieux-lyon":   ["presquile","perrache","fourviere"],
    "perrache":     ["presquile","vieux-lyon","gerland","confluence"],
    "gerland":      ["perrache","guillotiere"],
    "guillotiere":  ["presquile","part-dieu","gerland"],
    "brotteaux":    ["part-dieu","villette"],
    "villette":     ["brotteaux","part-dieu","montchat"],
    "montchat":     ["part-dieu","villette"],
    "fourviere":    ["vieux-lyon","presquile"],
    "croix-rousse": ["presquile","brotteaux"],
    "confluence":   ["perrache","vieux-lyon"],
}

ZONE_NAMES = {
    "part-dieu":    "Part-Dieu",
    "presquile":    "Presqu'île",
    "vieux-lyon":   "Vieux-Lyon",
    "perrache":     "Perrache",
    "gerland":      "Gerland",
    "guillotiere":  "Guillotière",
    "brotteaux":    "Brotteaux",
    "villette":     "La Villette",
    "montchat":     "Montchat",
    "fourviere":    "Fourvière",
    "croix-rousse": "Croix-Rousse",
    "confluence":   "Confluence",
}

SIGNAL_LABELS = {
    "traffic":   "Trafic",
    "weather":   "Météo",
    "event":     "Événement",
    "transport": "Transport TCL",
    "incident":  "Incidents",
}


def normalize(x: float, signal: str, bl: Dict[str, Dict[str, float]] = None) -> float:
    b = (bl or BASELINE)[signal]
    return (x - b["mu"]) / (b["sigma"] + EPSILON)


def compute_phi(dt: datetime = None) -> float:
    if dt is None:
        dt = datetime.now(LYON_TZ)
    else:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(LYON_TZ)

    t = dt.hour + dt.minute / 60.0  # heure décimale 0-24

    def _ramp(x: float, x0: float, x1: float, v0: float, v1: float) -> float:
        """Interpolation linéaire entre v0 et v1 sur [x0, x1]."""
        if x <= x0: return v0
        if x >= x1: return v1
        return v0 + (v1 - v0) * (x - x0) / (x1 - x0)

    # Calibré sur données réelles Lyon (TomTom 2025, CEREMA, EMD 2015)
    # Congestion: nuit ~5%, off-peak ~30%, rush matin ~80%, rush soir ~90%
    # Le rush soir est plus intense que le matin à Lyon
    if t < 5.0:  return 0.50                               # nuit (congestion ~5%)
    if t < 6.5:  return _ramp(t, 5.0,  6.5,  0.50, 1.0)  # réveil progressif
    if t < 7.0:  return _ramp(t, 6.5,  7.0,  1.0,  1.55) # montée rush matin
    if t < 9.5:  return _ramp(t, 7.0,  9.5,  1.55, 1.60) # rush matin (pic 8h-9h)
    if t < 10.5: return _ramp(t, 9.5,  10.5, 1.60, 1.10) # fin rush matin
    if t < 11.5: return 1.10                               # creux matinée (~30%)
    if t < 12.0: return _ramp(t, 11.5, 12.0, 1.10, 1.25) # montée midi (écoles 11h30)
    if t < 13.5: return 1.25                               # mini-pic déjeuner (~40%)
    if t < 14.5: return _ramp(t, 13.5, 14.5, 1.25, 1.05) # retour école/bureau 13h30
    if t < 16.0: return 1.05                               # après-midi calme (~25%)
    if t < 16.5: return _ramp(t, 16.0, 16.5, 1.05, 1.40) # sortie écoles 16h30
    if t < 17.0: return _ramp(t, 16.5, 17.0, 1.40, 1.75) # montée rush soir
    if t < 18.0: return 1.75                               # pic rush soir (congestion ~90%)
    if t < 19.5: return _ramp(t, 18.0, 19.5, 1.75, 1.30) # décrue rush soir
    if t < 21.0: return _ramp(t, 19.5, 21.0, 1.30, 1.00) # fin rush soir
    if t < 22.5: return _ramp(t, 21.0, 22.5, 1.00, 0.70) # soirée → nuit
    return _ramp(t, 22.5, 24.0, 0.70, 0.50)               # transition nuit profonde


def compute_risk(signals: dict, phi: float, bl: Dict = None) -> float:
    return phi * sum(WEIGHTS[s] * normalize(v, s, bl) for s, v in signals.items())


def compute_anomaly(signals: dict, bl: Dict = None) -> float:
    # max(z, 0) : on ne capte que les déviations positives (tension élevée).
    # abs(z) créait une anomalie forte même quand tous les signaux sont bas
    # (ex: nuit calme, trafic fluide → score MODÉRÉ alors que tout va bien).
    return sum(ALPHA[s] * max(normalize(v, s, bl), 0.0) for s, v in signals.items())


def _soft_gate(z: float, theta: float, k: float = 4.0) -> float:
    """Sigmoid soft-gate: 0 quand z << θ, ~1 quand z >> θ, 0.5 à z=θ."""
    return 1.0 / (1.0 + math.exp(-k * (z - theta)))


def compute_conv(signals: dict, bl: Dict = None) -> float:
    S = {s: normalize(v, s, bl) for s, v in signals.items()}
    pairs = [
        ("traffic",   "weather",   "traffic_weather"),
        ("traffic",   "event",     "traffic_event"),
        ("traffic",   "transport", "traffic_transport"),
        ("traffic",   "incident",  "traffic_incident"),
        ("weather",   "event",     "weather_event"),
        ("weather",   "transport", "weather_transport"),
        ("weather",   "incident",  "weather_incident"),
        ("event",     "transport", "event_transport"),
        ("event",     "incident",  "event_incident"),
        ("transport", "incident",  "transport_incident"),
    ]
    return sum(
        BETA[k] * _soft_gate(S[a], THETA[a]) * _soft_gate(S[b], THETA[b])
        for a, b, k in pairs
    )


def compute_alert(risk, anomaly, conv) -> float:
    return LAMBDA["l1"] * risk + LAMBDA["l2"] * anomaly + LAMBDA["l3"] * conv


def compute_spread(zone_id: str, alert_map: dict) -> float:
    nbrs = NEIGHBORS.get(zone_id, [])
    if not nbrs: return 0.0
    K = SPATIAL_KERNEL_DECAY / len(nbrs)
    return sum(K * max(alert_map.get(n, 0.0), 0.0) for n in nbrs)


def compute_urban_score(alert: float, spread: float) -> int:
    raw = alert + LAMBDA["l4"] * spread
    # Sigmoid mapping — préserve les seuils existants (CALME/MODÉRÉ/TENDU/CRITIQUE)
    # tout en étirant la plage haute pour mieux différencier TENDU et CRITIQUE.
    # Centre=1.5, k=0.6 → baseline(raw=0)≈29, TENDU à raw≈1.85, CRITIQUE à raw≈3.04
    normalized = 1.0 / (1.0 + math.exp(-0.6 * (raw - 1.5)))
    return int(max(0, min(100, normalized * 100)))


def score_level(score: int) -> str:
    if score < 35: return "CALME"
    if score < 55: return "MODÉRÉ"
    if score < 72: return "TENDU"
    return "CRITIQUE"


def top_causes(signals: dict, n: int = 3, bl: Dict = None) -> List[str]:
    scored = sorted(
        [(s, normalize(v, s, bl)) for s, v in signals.items()],
        key=lambda x: x[1],
        reverse=True
    )
    # Ne montrer que les déviations positives (signaux de tension).
    # Les valeurs négatives (trafic fluide, beau temps) ne sont pas des "causes".
    positive = [(s, v) for s, v in scored if v > 0.5]
    top = positive[:n]
    return [f"{SIGNAL_LABELS[s]} +{v:.1f}σ" for s, v in top]


def compute_forecast(
    current_score: int,
    alert: float,
    spread: float,
    dt: datetime = None,
    trend: float = 0.0,                         # points/min
    signals: dict = None,                        # signaux bruts — pour extraction incident
    incident_schedule: Dict[int, float] = None,  # {30: v, 60: v, 120: v} planifié
    bl: Dict = None,                             # baseline effective de la zone
) -> List[dict]:
    """
    Prévision probabiliste sur 30/60/120 min.
    Intègre :
      - phi futur (heures de pointe)
      - tendance récente (delta score / min)
      - persistance via decay exponentiel
      - incidents planifiés (starttime/endtime Criter) : remplace le decay incident
        par la valeur réelle à chaque horizon (ex: tunnel fermé à 20h anticipé à 19h)
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    phi_now = max(compute_phi(dt), 0.1)
    _bl = bl or BASELINE

    # Contribution incident courante dans l'alert (pour soustraction avant remplacement)
    incident_now  = (signals or {}).get("incident", 0.0)
    z_inc_now     = normalize(incident_now, "incident", _bl)
    inc_alert_now = (
        LAMBDA["l1"] * phi_now * WEIGHTS["incident"] * z_inc_now
        + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_now, 0.0)
    )

    results = []
    for h in FORECAST_HORIZONS:
        future_dt  = dt + timedelta(minutes=h)
        phi_future = compute_phi(future_dt)
        # Ratio phi cappé pour éviter qu'une nuit calme prédise TENDU au rush
        # Cap 1.8 : cohérent avec le ratio max Lyon (rush soir 1.75 / off-peak 1.05)
        phi_ratio  = min(phi_future / phi_now, 1.8)

        # Decay lent (tau=240) pour permettre au phi rush hour de compenser
        decay = math.exp(-h / 240)

        # Composante tendance — pondérée pour avoir un impact réel sur le score
        trend_decay   = math.exp(-h / 60)
        trend_contrib = max(-1.0, min(1.0, trend * h * trend_decay))

        fa  = alert * decay * phi_ratio
        fa += trend_contrib * 0.3

        # Remplacement incident planifié : si schedule disponible, on ne decay pas
        # l'incident — on utilise la valeur réelle à ce horizon depuis Criter
        if signals and incident_schedule and h in incident_schedule:
            z_inc_sched = normalize(incident_schedule[h], "incident", _bl)
            inc_alert_sched = (
                LAMBDA["l1"] * phi_future * WEIGHTS["incident"] * z_inc_sched
                + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_sched, 0.0)
            )
            # Soustraire la part incident décayée, ajouter la part planifiée
            fa = fa - inc_alert_now * decay * phi_ratio + inc_alert_sched

        fs = compute_urban_score(fa, spread * decay)
        fs = max(0, min(100, fs))

        results.append({
            "horizon_min": h,
            "urban_score": fs,
            "level":       score_level(fs),
            "phi":         round(phi_future, 2),
        })

    return results

def score_zone(zone_id: str, signals: dict, alert_map: dict, dt: datetime = None) -> dict:
    bl      = _effective_baseline(zone_id)
    phi     = compute_phi(dt)
    risk    = compute_risk(signals, phi, bl)
    anomaly = compute_anomaly(signals, bl)
    conv    = compute_conv(signals, bl)
    alert   = compute_alert(risk, anomaly, conv)
    spread  = compute_spread(zone_id, alert_map)
    urban   = compute_urban_score(alert, spread)
    S       = {s: round(normalize(v, s, bl), 3) for s, v in signals.items()}

    return {
        "zone_id":     zone_id,
        "zone_name":   ZONE_NAMES.get(zone_id, zone_id),
        "urban_score": urban,
        "level":       score_level(urban),
        "signals":     S,
        "raw_signals": dict(signals),
        "components":  {
            "risk":    round(risk, 4),
            "anomaly": round(anomaly, 4),
            "conv":    round(conv, 4),
            "spread":  round(spread, 4),
            "phi":     round(phi, 3),
        },
        "top_causes":  top_causes(signals, bl=bl),
        "alert":       alert,
        "timestamp":   (dt or datetime.now(timezone.utc)).isoformat(),
    }


def score_all_zones(all_signals: Dict[str, Dict[str, float]], dt: datetime = None) -> List[dict]:
    alert_map = {}
    for zone_id, signals in all_signals.items():
        bl      = _effective_baseline(zone_id)
        phi     = compute_phi(dt)
        risk    = compute_risk(signals, phi, bl)
        anomaly = compute_anomaly(signals, bl)
        conv    = compute_conv(signals, bl)
        alert_map[zone_id] = compute_alert(risk, anomaly, conv)
    return [score_zone(z, s, alert_map, dt) for z, s in all_signals.items()]