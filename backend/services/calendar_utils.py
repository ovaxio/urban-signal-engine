"""
Urban Signal Engine — Calendar Utilities
=========================================
Calendrier scolaire, jours fériés, et classification des types de jour
pour le profil temporel φ du moteur de scoring.

Chargé dynamiquement depuis la DB (refresh tous les 3 mois via API education.gouv.fr).
Fallback hardcodé si la DB est vide (premier démarrage).
"""

import logging
from datetime import date, timedelta
from typing import List, Tuple

_log = logging.getLogger("calendar_utils")


# ─── Vacances scolaires (fallback) ───────────────────────────────────────────

_FALLBACK_VACANCES: List[Tuple[date, date]] = [
    # 2025-2026 — Zone A (Lyon) — source : education.gouv.fr
    (date(2025, 10, 18), date(2025, 11, 3)),   # Toussaint
    (date(2025, 12, 20), date(2026, 1, 5)),     # Noël
    (date(2026, 2, 7),   date(2026, 2, 23)),    # Hiver
    (date(2026, 4, 4),   date(2026, 4, 20)),    # Printemps
    (date(2026, 7, 4),   date(2026, 9, 1)),     # Été
    # 2026-2027 — Zone A (Lyon)
    (date(2026, 10, 17), date(2026, 11, 2)),    # Toussaint
    (date(2026, 12, 19), date(2027, 1, 4)),     # Noël
    (date(2027, 2, 13),  date(2027, 3, 1)),     # Hiver
    (date(2027, 4, 10),  date(2027, 4, 26)),    # Printemps
    (date(2027, 7, 3),   date(2027, 9, 1)),     # Été
]

# Jours fériés fixes + calcul automatique des mobiles (Pâques)
_JOURS_FERIES_FIXES = [(1, 1), (5, 1), (5, 8), (7, 14), (8, 15), (11, 1), (11, 11), (12, 25)]


# ─── Easter / jours fériés ────────────────────────────────────────────────────

def _easter(year: int) -> date:
    """Calcul de Pâques — algorithme de Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _jours_feries(year: int) -> List[date]:
    """Retourne tous les jours fériés français pour une année."""
    fixed = [date(year, m, d) for m, d in _JOURS_FERIES_FIXES]
    e = _easter(year)
    mobile = [
        e + timedelta(days=1),   # Lundi de Pâques
        e + timedelta(days=39),  # Ascension
        e + timedelta(days=50),  # Lundi de Pentecôte
    ]
    return fixed + mobile


# ─── Caches mémoire ──────────────────────────────────────────────────────────

_vacances_cache: List[Tuple[date, date]] = list(_FALLBACK_VACANCES)
_feries_cache: set = set()
for _y in range(2025, 2028):
    _feries_cache.update(_jours_feries(_y))


def load_vacances_from_db() -> None:
    """Charge les vacances depuis la table calendar_vacances (si elle existe)."""
    global _vacances_cache
    try:
        from services.storage import get_vacances
        rows = get_vacances()
        if rows:
            _vacances_cache = [(r["start"], r["end"]) for r in rows]
            _log.info("Calendrier scolaire chargé depuis DB : %d périodes", len(_vacances_cache))
    except Exception:
        pass  # fallback hardcodé


def is_vacances(d: date) -> bool:
    return any(start <= d <= end for start, end in _vacances_cache)


def is_ferie(d: date) -> bool:
    if d.year not in {dd.year for dd in _feries_cache}:
        _feries_cache.update(_jours_feries(d.year))
    return d in _feries_cache


def day_type(dt) -> str:
    """
    Retourne le type de jour pour le profil φ :
      'weekend'   — samedi, dimanche, jour férié
      'vacances'  — jour de semaine en vacances scolaires
      'mercredi'  — mercredi hors vacances
      'semaine'   — lun, mar, jeu, ven hors vacances
    """
    from datetime import datetime
    d = dt.date() if isinstance(dt, datetime) else dt
    dow = d.weekday()  # 0=lundi … 6=dimanche

    if dow >= 5 or is_ferie(d):
        return "weekend"
    if is_vacances(d):
        return "vacances"
    if dow == 2:  # mercredi
        return "mercredi"
    return "semaine"
