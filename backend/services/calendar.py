"""
Urban Signal Engine — Calendar Service
Fetch des vacances scolaires Zone A (Lyon) depuis l'API data.education.gouv.fr.
Refresh automatique tous les 3 mois.
"""

import logging
from datetime import date, datetime, timezone
from typing import List, Dict, Any

import httpx

from services.storage import get_vacances, save_vacances

log = logging.getLogger("calendar")

# API ouverte — pas de clé requise pour les données publiques
EDUCATION_API_URL = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets"
    "/fr-en-calendrier-scolaire/records"
)

# Zone A = Académie de Lyon (+ Besançon, Bordeaux, Clermont, Dijon, Grenoble, Limoges, Poitiers)
ZONE = "A"


async def fetch_vacances_scolaires() -> List[Dict[str, Any]]:
    """
    Récupère les vacances scolaires Zone A depuis l'API education.gouv.fr.
    Retourne une liste de {start: date, end: date, description: str}.
    """
    today = date.today()
    # Récupérer les 2 prochaines années scolaires
    year_start = today.year if today.month >= 9 else today.year - 1

    params = {
        "limit": 50,
        "offset": 0,
        "where": f'zones = "{ZONE}" AND annee_scolaire >= "{year_start}-{year_start+1}"',
        "order_by": "start_date",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(EDUCATION_API_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("Fetch vacances scolaires échoué : %s", e)
        return []

    results = data.get("results", [])
    if not results:
        log.warning("Aucune vacance trouvée dans l'API education.gouv.fr")
        return []

    periods = []
    for record in results:
        start_s = record.get("start_date")
        end_s = record.get("end_date")
        desc = record.get("description", "")

        if not start_s or not end_s:
            continue

        try:
            start = date.fromisoformat(start_s[:10])
            end = date.fromisoformat(end_s[:10])
        except (ValueError, TypeError):
            continue

        periods.append({
            "start": start,
            "end": end,
            "description": desc,
        })

    log.info("API education.gouv.fr : %d périodes de vacances Zone A récupérées", len(periods))
    return periods


async def refresh_vacances() -> int:
    """
    Fetch les vacances depuis l'API et les sauvegarde en DB.
    Recharge le cache scoring.
    Retourne le nombre de périodes sauvegardées.
    """
    periods = await fetch_vacances_scolaires()
    if not periods:
        log.warning("Refresh vacances : aucune donnée, cache conservé")
        return 0

    count = save_vacances(periods)

    # Recharger le cache dans le module scoring
    try:
        from services.scoring import load_vacances_from_db
        load_vacances_from_db()
    except Exception as e:
        log.warning("Rechargement cache scoring échoué : %s", e)

    return count
