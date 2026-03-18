# services/events.py
# Signal event — Calendrier statique Lyon 2026
# Fallback propre en attendant une vraie source API événementielle sur Lyon

import logging
import math
from datetime import date, timedelta
from typing import Dict, List

from config import ZONE_CENTROIDS

log = logging.getLogger("service.events")

EVENT_RADIUS_KM = 1.2


def _days(start: str, end: str) -> List[date]:
    """Génère la liste des dates entre start et end inclus (format YYYY-MM-DD)."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


# ──────────────────────────────────────────────
# Calendrier statique Lyon 2026
# Sources : Office du Tourisme Lyon, Lyon Première, agenda.grandlyon.com
# ──────────────────────────────────────────────
STATIC_EVENTS: List[dict] = [
    # --- Q1 ---
    {
        "name":   "Foire de Lyon (Eurexpo)",
        "dates":  _days("2026-03-20", "2026-03-30"),
        "zone":   "villette",       # Eurexpo → zone villette/est
        "lat":    45.7310, "lng": 4.9220,
        "weight": 1.5,
    },
    {
        "name":   "Lyon Urban Trail",
        "dates":  [date(2026, 3, 29)],
        "zone":   "fourviere",
        "lat":    45.7600, "lng": 4.8200,
        "weight": 1.2,
    },
    # --- Q2 ---
    {
        "name":   "Quais du Polar",
        "dates":  _days("2026-04-03", "2026-04-05"),
        "zone":   "presquile",
        "lat":    45.7560, "lng": 4.8320,
        "weight": 0.8,
    },
    {
        "name":   "Nuits Sonores",
        "dates":  _days("2026-05-13", "2026-05-17"),
        "zone":   "confluence",
        "lat":    45.7380, "lng": 4.8170,
        "weight": 1.0,
    },
    {
        "name":   "Les Intergalactiques",
        "dates":  _days("2026-06-05", "2026-06-07"),
        "zone":   "part-dieu",
        "lat":    45.7600, "lng": 4.8600,
        "weight": 0.8,
    },
    {
        "name":   "Fête de la Musique",
        "dates":  [date(2026, 6, 21)],
        "zone":   "presquile",
        "lat":    45.7600, "lng": 4.8350,
        "weight": 1.0,
    },
    {
        "name":   "Lyon Street Food Festival",
        "dates":  _days("2026-06-11", "2026-06-14"),
        "zone":   "gerland",
        "lat":    45.7330, "lng": 4.8330,
        "weight": 0.8,
    },
    # --- Q3 ---
    {
        "name":   "Nuits de Fourvière (saison)",
        "dates":  _days("2026-05-28", "2026-07-25"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,    # impact quotidien modéré, boost les soirs de gros concerts
    },
    {
        "name":   "Biennale de la Danse / d'Art Contemporain",
        "dates":  _days("2026-09-10", "2026-10-10"),
        "zone":   "presquile",
        "lat":    45.7560, "lng": 4.8320,
        "weight": 1.0,
    },
    # --- Q4 ---
    {
        "name":   "Run in Lyon",
        "dates":  [date(2026, 10, 4)],
        "zone":   "gerland",
        "lat":    45.7330, "lng": 4.8330,
        "weight": 1.2,
    },
    {
        "name":   "Festival Lumière",
        "dates":  _days("2026-10-10", "2026-10-18"),
        "zone":   "part-dieu",
        "lat":    45.7600, "lng": 4.8600,
        "weight": 1.2,
    },
    {
        "name":   "Equita Lyon (Eurexpo)",
        "dates":  _days("2026-10-28", "2026-11-01"),
        "zone":   "villette",
        "lat":    45.7310, "lng": 4.9220,
        "weight": 1.2,
    },
    # Fête des Lumières — ~2M visiteurs sur 4 nuits, Lyon paralysée
    # Sites principaux : poids 0.7 (épicentres CRITIQUE)
    # Gares d'accès (Part-Dieu, Perrache) : poids 0.3 (saturation transport TENDU)
    {
        "name":   "Fête des Lumières — Presqu'île",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "presquile",
        "lat":    45.7580, "lng": 4.8330,
        "weight": 0.7,
    },
    {
        "name":   "Fête des Lumières — Fourvière",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,
    },
    {
        "name":   "Fête des Lumières — Vieux Lyon",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "vieux-lyon",
        "lat":    45.7622, "lng": 4.8271,
        "weight": 0.7,
    },
    {
        "name":   "Fête des Lumières — Croix-Rousse",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "croix-rousse",
        "lat":    45.7760, "lng": 4.8320,
        "weight": 0.7,
    },
    {
        "name":   "Fête des Lumières — Parc de la Tête d'Or",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "brotteaux",
        "lat":    45.7720, "lng": 4.8570,   # entrée sud du parc, dans le rayon Brotteaux
        "weight": 0.7,
    },
    {
        "name":   "Fête des Lumières — Gare Part-Dieu (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 0.3,
    },
    {
        "name":   "Fête des Lumières — Gare Perrache (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "perrache",
        "lat":    45.7488, "lng": 4.8286,
        "weight": 0.3,
    },
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _active_events(today: date = None) -> List[dict]:
    if today is None:
        today = date.today()
    return [ev for ev in STATIC_EVENTS if today in ev["dates"]]


# ──────────────────────────────────────────────
# Scoring event → signal float par zone
# ──────────────────────────────────────────────

def compute_event_signals(today: date = None) -> Dict[str, float]:
    """
    Retourne {zone_id: event_signal_float} pour la date donnée.
    Signal ∈ [0.0, 3.0] — cohérent avec les autres signaux du moteur.
    Zone sans event = 0.0 → normalisé légèrement négatif (effet "calme").
    """
    scores: Dict[str, float] = {z: 0.0 for z in ZONE_CENTROIDS}
    active = _active_events(today)

    if not active:
        log.info("Event signals: aucun événement actif aujourd'hui.")
        return scores

    for ev in active:
        for zone_id, (zlat, zlng) in ZONE_CENTROIDS.items():
            dist = _haversine_km(ev["lat"], ev["lng"], zlat, zlng)
            if dist <= EVENT_RADIUS_KM:
                proximity = 1.0 - (dist / EVENT_RADIUS_KM)
                scores[zone_id] += ev["weight"] * proximity

    result = {z: round(min(v, 3.0), 4) for z, v in scores.items()}
    active_zones = {z: v for z, v in result.items() if v > 0}
    log.info(f"Event signals: {len(active)} événement(s) actif(s) → zones impactées: {active_zones}")
    return result


# ──────────────────────────────────────────────
# Point d'entrée pour ingestion.py
# ──────────────────────────────────────────────

async def fetch_event_signals() -> Dict[str, float]:
    """
    Appelé par ingestion.py — retourne {zone_id: float} prêt à injecter.
    Async pour compatibilité avec asyncio.gather dans ingestion.py.
    """
    return compute_event_signals()
