"""
Urban Signal Engine — Smoothing Service
Lissage EWM (Exponential Weighted Mean) sur les raw_signals
avant passage dans le moteur de scoring.

Principe :
  signal_lissé = α·x_t + (1-α)·x_{t-1} + (1-α)²·x_{t-2} + ...
  α = 0.4  → réactivité modérée, bruit atténué

Flow :
  raw_signals (ingestion)
      → smooth_signals() → raw lissés
      → score_all_zones() → normalize() → scoring
"""

import logging
from typing import Dict, Optional

from services.storage import get_zone_history

log = logging.getLogger("smoothing")

SIGNALS = ("traffic", "weather", "event", "transport", "incident")
ALPHA   = 0.4   # facteur de lissage — plus proche de 1 = plus réactif
WINDOW  = 6     # nb de relevés passés utilisés (≈ 12 min à refresh 120s)
MIN_ROWS = 3    # minimum pour activer le lissage

# Bornes de validité sur valeurs BRUTES
VALID_RANGE = {
    "traffic":   (0.5, 3.0),
    "weather":   (0.0, 3.0),
    "event":     (0.0, 3.0),
    "transport": (0.0, 1.0),
    "incident":  (0.0, 3.0),
}


def ewm(values: list[float], alpha: float = ALPHA) -> float:
    """
    Calcule la moyenne exponentielle pondérée d'une série.
    `values` doit être ordonnée du plus ancien au plus récent.
    """
    if not values:
        raise ValueError("Liste vide — impossible de lisser.")
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result


def smooth_signals(
    zone_id: str,
    current: Dict[str, float],
    window: int = WINDOW,
) -> Dict[str, float]:
    """
    Retourne les signaux bruts lissés pour une zone.

    - Récupère les `window` derniers relevés raw en base.
    - Pour chaque signal, calcule l'EWM sur [historique raw + valeur courante].
    - Si pas assez d'historique, retourne les signaux bruts sans lissage.

    Paramètres :
        zone_id  : identifiant de la zone
        current  : dict des raw signals du cycle courant
        window   : nb de relevés historiques à inclure

    Retourne :
        dict signal → valeur lissée (même structure que `current`)
    """
    try:
        # source='live' → exclut les données seed pour éviter un saut
        # artificiel entre le seed (données pré-deploy) et les données live.
        rows = get_zone_history(zone_id, limit=window, source="live")
    except Exception as e:
        log.warning("smooth_signals(%s) : erreur lecture historique — %s", zone_id, e)
        return current

    if len(rows) < MIN_ROWS:
        log.debug("smooth_signals(%s) : historique live insuffisant (%d rows) — pas de lissage", zone_id, len(rows))
        return current

    # rows trié du plus récent au plus ancien → on inverse
    rows_asc = list(reversed(rows))

    smoothed = {}
    for signal in SIGNALS:
        if signal not in current:
            continue

        lo, hi = VALID_RANGE.get(signal, (0.0, 3.0))
        raw_col = f"raw_{signal}"

        # Historique depuis colonnes raw_
        hist_values = [
            r[raw_col] for r in rows_asc
            if r.get(raw_col) is not None and lo <= r[raw_col] <= hi
        ]

        # Valeur courante en fin de série
        cur_val = current.get(signal)
        if cur_val is None:
            smoothed[signal] = current.get(signal)
            continue

        series = hist_values + [cur_val]

        if len(series) < 2:
            # Pas assez d'historique raw pour ce signal — valeur brute
            smoothed[signal] = cur_val
        else:
            smoothed[signal] = round(ewm(series), 4)

    log.debug(
        "smooth_signals(%s) : brut=%s lissé=%s (window=%d rows=%d)",
        zone_id, current, smoothed, window, len(rows)
    )
    return smoothed