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
    # hours = (start_hour, end_hour) — créneau d'activité de l'événement.
    # Utilisé par la simulation pré-événement (pas le scoring live).
    # ramp = heures d'arrivée/départ autour du créneau (afflux transport).
    {
        "name":   "Foire de Lyon (Eurexpo)",
        "dates":  _days("2026-03-20", "2026-03-30"),
        "zone":   "part-dieu",      # impact réel = transit (T3 tram, 80% visiteurs via Part-Dieu)
        "lat":    45.7605, "lng": 4.8597,  # Gare Part-Dieu (hub de transit vers Eurexpo)
        "weight": 1.2,              # réduit vs 1.5 : impact indirect (transit), pas direct (lieu)
        "hours":  (9, 19),          # salon pro/public journée
        "ramp":   2,
    },
    {
        "name":   "Lyon Urban Trail",
        "dates":  [date(2026, 3, 29)],
        "zone":   "vieux-lyon",     # départ Quai Fulchiron, arrivée Place Saint-Jean
        "lat":    45.7594, "lng": 4.8275,
        "weight": 1.2,
        "hours":  (7, 16),          # premier départ 7h (38km), arrivées jusqu'à ~16h
        "ramp":   1,
    },
    # --- OL Ligue 1 (Groupama Stadium, Décines) ---
    # Impact principal = transit Part-Dieu (T3 tram, gare TGV) + afflux centre-ville.
    # 55 000 spectateurs → saturation T3, bouchons A43/Bd périph, bars Presqu'île.
    {
        "name":   "OL — PSG (Ligue 1, Groupama Stadium)",
        "dates":  [date(2026, 4, 5)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,   # Gare Part-Dieu (hub transit vers Décines)
        "weight": 1.8,                       # affiche majeure, 55k+ spectateurs
        "hours":  (21, 23),                  # coup d'envoi 21h00
        "ramp":   3,                         # fans arrivent dès 18h, départ jusqu'à 00h
    },
    {
        "name":   "OL — OM (Ligue 1, Groupama Stadium)",
        "dates":  [date(2026, 5, 10)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 1.8,
        "hours":  (15, 17),                  # coup d'envoi 15h00
        "ramp":   3,
    },
    {
        "name":   "OL — Saint-Étienne (Derby, Groupama Stadium)",
        "dates":  [date(2026, 3, 22)],
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 2.0,                       # derby = tension maximale
        "hours":  (17, 19),                  # coup d'envoi 17h00
        "ramp":   3,
    },
    # --- Q2 ---
    {
        "name":   "Quais du Polar",
        "dates":  _days("2026-04-03", "2026-04-05"),
        "zone":   "presquile",
        "lat":    45.7640, "lng": 4.8340,  # Hôtel de Ville / Palais de la Bourse
        "weight": 0.8,
        "hours":  (10, 22),         # festival littéraire journée + soirée
        "ramp":   1,
    },
    {
        "name":   "Nuits Sonores",
        "dates":  _days("2026-05-13", "2026-05-17"),
        "zone":   "confluence",
        "lat":    45.7364, "lng": 4.8150,  # La Sucrière, quai Rambaud
        "weight": 1.0,
        "hours":  (16, 23),         # Days 16h + Nuits 22h → couvert par 16-23
        "ramp":   2,
    },
    {
        "name":   "Les Intergalactiques",
        "dates":  _days("2026-06-05", "2026-06-07"),
        "zone":   "part-dieu",
        "lat":    45.7600, "lng": 4.8600,
        "weight": 0.8,
        "hours":  (14, 22),         # convention SF après-midi + soirée
        "ramp":   1,
    },
    {
        "name":   "Fête de la Musique",
        "dates":  [date(2026, 6, 21)],
        "zone":   "presquile",
        "lat":    45.7600, "lng": 4.8350,
        "weight": 1.0,
        "hours":  (17, 23),         # concerts en plein air fin d'après-midi → nuit
        "ramp":   1,
    },
    {
        "name":   "Lyon Street Food Festival",
        "dates":  _days("2026-06-11", "2026-06-14"),
        "zone":   "confluence",     # Grandes Locos, La Mulatière (nearest zone)
        "lat":    45.7212, "lng": 4.8159,
        "weight": 0.8,
        "hours":  (11, 23),         # food festival midi → soirée
        "ramp":   1,
    },
    # --- Q3 ---
    {
        "name":   "Nuits de Fourvière (saison)",
        "dates":  _days("2026-05-28", "2026-07-25"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.5,    # impact quotidien modéré, boost les soirs de gros concerts
        "hours":  (20, 23),         # spectacles en soirée
        "ramp":   2,
    },
    {
        "name":   "Biennale d'Art Contemporain",
        "dates":  _days("2026-09-19", "2026-12-31"),  # Sep 19 → ~Jan 3 2027
        "zone":   "gerland",        # Usines Fagor (29 000 m², plus grand site)
        "lat":    45.7260, "lng": 4.8340,
        "weight": 1.0,
        "hours":  (10, 19),         # expositions journée
        "ramp":   1,
    },
    # --- Q4 ---
    {
        "name":   "Run in Lyon",
        "dates":  [date(2026, 10, 4)],
        "zone":   "presquile",      # départ Vieux-Lyon, arrivée/village Place Bellecour
        "lat":    45.7545, "lng": 4.8260,
        "weight": 1.2,
        "hours":  (7, 15),          # marathon départ 8h, arrivées jusqu'à ~14h30
        "ramp":   1,
    },
    {
        "name":   "Festival Lumière",
        "dates":  _days("2026-10-10", "2026-10-18"),
        "zone":   "montchat",       # Institut Lumière, 25 rue du Premier Film (Lyon 8e)
        "lat":    45.7450, "lng": 4.8706,
        "weight": 1.2,
        "hours":  (10, 23),         # séances cinéma toute la journée
        "ramp":   1,
    },
    {
        "name":   "Equita Lyon (Eurexpo)",
        "dates":  _days("2026-10-28", "2026-11-01"),
        "zone":   "part-dieu",      # impact réel = transit (T3 tram vers Eurexpo)
        "lat":    45.7605, "lng": 4.8597,  # Gare Part-Dieu
        "weight": 1.0,              # réduit : impact indirect (transit)
        "hours":  (8, 20),          # salon 9h-19h, samedi jusqu'à 22h30
        "ramp":   2,
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
        "hours":  (18, 23),         # illuminations nocturnes
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Fourvière",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "fourviere",
        "lat":    45.7622, "lng": 4.8200,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Vieux Lyon",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "vieux-lyon",
        "lat":    45.7622, "lng": 4.8271,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Croix-Rousse",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "croix-rousse",
        "lat":    45.7760, "lng": 4.8320,
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Parc de la Tête d'Or",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "brotteaux",
        "lat":    45.7720, "lng": 4.8570,   # entrée sud du parc, dans le rayon Brotteaux
        "weight": 0.7,
        "hours":  (18, 23),
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Gare Part-Dieu (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "part-dieu",
        "lat":    45.7605, "lng": 4.8597,
        "weight": 0.3,
        "hours":  (16, 23),         # afflux gare dès 16h
        "ramp":   2,
    },
    {
        "name":   "Fête des Lumières — Gare Perrache (accès)",
        "dates":  _days("2026-12-05", "2026-12-08"),
        "zone":   "perrache",
        "lat":    45.7488, "lng": 4.8286,
        "weight": 0.3,
        "hours":  (16, 23),         # afflux gare dès 16h
        "ramp":   2,
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
