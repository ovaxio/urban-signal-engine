"""
Urban Signal Engine — Scoring Module
=====================================

Modèle de détection de tensions urbaines en temps réel sur 12 zones lyonnaises.

UrbanScore (0–100)
------------------
Transformation sigmoid de la somme alert + λ₄·spread.

    score = sigmoid(alert + λ₄ · spread) × 100

    où  alert  = λ₁·RISK + λ₂·ANOMALY + λ₃·CONV
        spread = K · Σ max(alert_voisin, 0)

Sémantique du score :
    0–34   CALME     Fonctionnement normal, aucun signal notable.
    35–54  MODÉRÉ    Signaux faibles, attention recommandée.
    55–71  TENDU     Tension confirmée, surveillance active.
    72–100 CRITIQUE  Convergence de signaux forts, intervention possible.

La sigmoid est centrée à raw=1.5 (k=0.6), donc :
    - score ≈ 29  quand raw=0 (tous signaux au niveau baseline)
    - score = 50   quand raw=1.5 (tension médiane du modèle)
    - score ≈ 72  quand raw=3.0 (seuil CRITIQUE)
Score 50 n'est PAS « absence de tension » mais « niveau médian ».
Un score neutre (signaux au baseline) se situe autour de 29.

Composantes
-----------
RISK = φ(t) × Σ(wₛ × zₛ)
    Risque pondéré modulé par le profil temporel φ.
    φ amplifie les signaux au rush et les atténue la nuit.
    Attention : φ amplifie aussi le bruit résiduel — le lissage EWM
    (α=0.4, fenêtre=6) en amont est donc essentiel.

ANOMALY = Σ(αₛ × max(zₛ, 0))
    Détection de pics individuels. Asymétrique (ReLU) : seuls les
    z-scores positifs contribuent. Un signal « trop calme » ne réduit
    pas l'anomalie — choix intentionnel pour éviter qu'une nuit sans
    trafic ne génère une fausse anomalie négative.

CONV = min(Σ(βₖ × gate(zₐ) × gate(zᵦ)), 2.0)
    Convergence : co-occurrence de signaux élevés. Bornée à 2.0
    (théorique max ≈ 3.20) pour limiter la surpondération.
    En pratique, conv ≤ 13% de l'alert dans le pire cas observé.

SPREAD = K × Σ max(alert_voisin, 0)
    Diffusion spatiale de tension. Positif uniquement : un voisin calme
    ne « soulage » pas la zone — la tension est locale, le spread
    modélise la contagion, pas la diffusion thermique.

Double comptage
---------------
Un même signal élevé alimente RISK, ANOMALY et CONV simultanément.
C'est intentionnel : les trois composantes capturent des aspects
différents (niveau global, pic individuel, co-occurrence). Une vraie
tension (signaux élevés ET corrélés) est ainsi fortement amplifiée par
rapport à un signal isolé élevé.
"""

import math
from datetime import datetime, date, timezone, timedelta
from typing import List, Dict, Tuple
from zoneinfo import ZoneInfo

LYON_TZ = ZoneInfo("Europe/Paris")

from config import (
    EPSILON, WEIGHTS, LAMBDA, THETA, ALPHA, BETA,
    SPATIAL_KERNEL_DECAY, FORECAST_HORIZONS,
)

import logging as _logging
_log = _logging.getLogger("scoring")


# ─── Validations au démarrage (fail-fast) ────────────────────────────────────

def _validate_config() -> None:
    """Vérifie la cohérence des hyperparamètres au chargement du module.
    Appelé une seule fois à l'import — erreur bloquante = startup interrompu."""
    import config as _cfg  # relecture dynamique pour testabilité

    # B.1 — Σβ_k ≤ CONV_BETA_SUM_MAX
    beta_sum = sum(BETA.values())
    if beta_sum > _cfg.CONV_BETA_SUM_MAX:
        raise ValueError(
            f"Σβ_k = {beta_sum:.2f} dépasse la borne CONV_BETA_SUM_MAX = {_cfg.CONV_BETA_SUM_MAX}. "
            f"Ajuster les BETA dans config.py ou augmenter CONV_BETA_SUM_MAX."
        )

    # C — Vérifier que sigmoid(0 − θ) < ε pour chaque θ (fond résiduel conv)
    # soft_gate(0, θ, k=4) = 1 / (1 + exp(k·θ))
    for signal, theta in THETA.items():
        gate_at_zero = 1.0 / (1.0 + math.exp(4.0 * theta))
        if gate_at_zero >= _cfg.CONV_THETA_EPSILON:
            _log.warning(
                "θ[%s] = %.2f trop bas : sigmoid(0 − θ) = %.4f ≥ ε = %.2f. "
                "Conv aura un fond résiduel non négligeable au régime neutre.",
                signal, theta, gate_at_zero, _cfg.CONV_THETA_EPSILON,
            )

    # Σw_s = 1.0
    w_sum = sum(WEIGHTS.values())
    if abs(w_sum - 1.0) > 0.01:
        _log.warning("Σ WEIGHTS = %.3f ≠ 1.0 — risk ne sera pas normalisé.", w_sum)


_validate_config()


# ─── Calendrier scolaire & jours fériés ───────────────────────────────────
# Chargé dynamiquement depuis la DB (refresh tous les 3 mois via API education.gouv.fr)
# Fallback hardcodé si la DB est vide (premier démarrage)

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


# Cache mémoire — rempli au démarrage depuis la DB, fallback hardcodé
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
            import logging
            logging.getLogger("scoring").info(
                "Calendrier scolaire chargé depuis DB : %d périodes", len(_vacances_cache)
            )
    except Exception:
        pass  # fallback hardcodé


def _is_vacances(d: date) -> bool:
    return any(start <= d <= end for start, end in _vacances_cache)


def _is_ferie(d: date) -> bool:
    # Recalcul dynamique si l'année n'est pas en cache
    if d.year not in {dd.year for dd in _feries_cache}:
        _feries_cache.update(_jours_feries(d.year))
    return d in _feries_cache


def _day_type(dt: datetime) -> str:
    """
    Retourne le type de jour pour le profil φ :
      'weekend'   — samedi, dimanche, jour férié
      'vacances'  — jour de semaine en vacances scolaires (pas d'école, commuters présents)
      'mercredi'  — mercredi hors vacances (pas d'école l'après-midi)
      'semaine'   — lun, mar, jeu, ven hors vacances (profil standard)
    """
    d = dt.date() if isinstance(dt, datetime) else dt
    dow = d.weekday()  # 0=lundi … 6=dimanche

    if dow >= 5 or _is_ferie(d):
        return "weekend"
    if _is_vacances(d):
        return "vacances"
    if dow == 2:  # mercredi
        return "mercredi"
    return "semaine"

BASELINE = {
    "traffic":   {"mu": 1.05, "sigma": 0.15},   # Criter : V≈1.0, O≈2.0, R≈2.8, N≈3.0 — recalibré auto
    "weather":   {"mu": 0.3,  "sigma": 0.35},
    "event":     {"mu": 0.2,  "sigma": 0.3},     # non-stationnaire — exclu de la calibration auto
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


def _ramp(x: float, x0: float, x1: float, v0: float, v1: float) -> float:
    """Interpolation linéaire entre v0 et v1 sur [x0, x1]."""
    if x <= x0: return v0
    if x >= x1: return v1
    return v0 + (v1 - v0) * (x - x0) / (x1 - x0)


def _phi_semaine(t: float) -> float:
    """Profil semaine standard (lun, mar, jeu, ven hors vacances).
    Calibré sur données réelles Lyon (Criter, CEREMA, EMD 2015).
    Congestion: nuit ~5%, off-peak ~30%, rush matin ~80%, rush soir ~90%.
    Le rush soir est plus intense que le matin à Lyon."""
    if t < 5.0:  return 0.50                               # nuit (~5%)
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
    if t < 18.0: return 1.75                               # pic rush soir (~90%)
    if t < 19.5: return _ramp(t, 18.0, 19.5, 1.75, 1.30) # décrue rush soir
    if t < 21.0: return _ramp(t, 19.5, 21.0, 1.30, 1.00) # fin rush soir
    if t < 22.5: return _ramp(t, 21.0, 22.5, 1.00, 0.70) # soirée → nuit
    return _ramp(t, 22.5, 24.0, 0.70, 0.50)               # transition nuit profonde


def _phi_mercredi(t: float) -> float:
    """Profil mercredi hors vacances.
    Pas d'école l'après-midi → pas de pic écoles 11h30/16h30.
    Rush matin identique (commuters). Rush soir atténué (-15%, école matin seul)."""
    if t < 5.0:  return 0.50
    if t < 6.5:  return _ramp(t, 5.0,  6.5,  0.50, 1.0)
    if t < 7.0:  return _ramp(t, 6.5,  7.0,  1.0,  1.55) # rush matin identique
    if t < 9.5:  return _ramp(t, 7.0,  9.5,  1.55, 1.60)
    if t < 10.5: return _ramp(t, 9.5,  10.5, 1.60, 1.10)
    if t < 11.5: return 1.10                               # creux matinée
    if t < 12.5: return _ramp(t, 11.5, 12.5, 1.10, 1.30) # sortie école matin (12h)
    if t < 13.5: return _ramp(t, 12.5, 13.5, 1.30, 1.05) # retour calme
    if t < 16.5: return 1.05                               # après-midi calme (pas d'école)
    if t < 17.0: return _ramp(t, 16.5, 17.0, 1.05, 1.55) # rush soir commuters seulement
    if t < 18.0: return 1.55                               # pic soir atténué (-15%)
    if t < 19.5: return _ramp(t, 18.0, 19.5, 1.55, 1.20)
    if t < 21.0: return _ramp(t, 19.5, 21.0, 1.20, 1.00)
    if t < 22.5: return _ramp(t, 21.0, 22.5, 1.00, 0.70)
    return _ramp(t, 22.5, 24.0, 0.70, 0.50)


def _phi_vacances(t: float) -> float:
    """Profil vacances scolaires (jours de semaine).
    Commuters présents mais pas d'effet école → rush atténué (~-20%).
    Pas de pics 11h30/16h30. Midi réduit."""
    if t < 5.0:  return 0.50
    if t < 6.5:  return _ramp(t, 5.0,  6.5,  0.50, 0.90)
    if t < 7.0:  return _ramp(t, 6.5,  7.0,  0.90, 1.30) # rush matin allégé
    if t < 9.5:  return _ramp(t, 7.0,  9.5,  1.30, 1.35) # pic matin -20%
    if t < 10.5: return _ramp(t, 9.5,  10.5, 1.35, 1.00)
    if t < 12.0: return 1.00                               # matinée calme
    if t < 13.5: return _ramp(t, 12.0, 13.5, 1.00, 1.10) # midi léger
    if t < 14.5: return _ramp(t, 13.5, 14.5, 1.10, 1.00)
    if t < 16.5: return 1.00                               # après-midi calme
    if t < 17.0: return _ramp(t, 16.5, 17.0, 1.00, 1.45) # rush soir allégé
    if t < 18.0: return 1.45                               # pic soir -20%
    if t < 19.5: return _ramp(t, 18.0, 19.5, 1.45, 1.15)
    if t < 21.0: return _ramp(t, 19.5, 21.0, 1.15, 0.90)
    if t < 22.5: return _ramp(t, 21.0, 22.5, 0.90, 0.65)
    return _ramp(t, 22.5, 24.0, 0.65, 0.50)


def _phi_weekend(t: float) -> float:
    """Profil weekend et jours fériés.
    Pas de rush commuter. Pic commercial 10h-18h (shopping Part-Dieu, Confluence).
    Congestion ~40-50% du pic semaine (Criter/CEREMA). Samedi > dimanche mais profil unique."""
    if t < 7.0:  return 0.45                               # nuit/grasse mat
    if t < 9.0:  return _ramp(t, 7.0,  9.0,  0.45, 0.70) # réveil lent
    if t < 10.0: return _ramp(t, 9.0,  10.0, 0.70, 0.90) # montée shopping
    if t < 12.0: return 0.90                               # pic commercial matin
    if t < 13.5: return _ramp(t, 12.0, 13.5, 0.90, 0.95) # midi/restau
    if t < 14.5: return 0.95                               # début après-midi
    if t < 17.0: return _ramp(t, 14.5, 17.0, 0.95, 1.00) # pic après-midi
    if t < 18.5: return 1.00                               # pic commercial soir
    if t < 20.0: return _ramp(t, 18.5, 20.0, 1.00, 0.75) # fermeture commerces
    if t < 22.0: return _ramp(t, 20.0, 22.0, 0.75, 0.55) # soirée
    return _ramp(t, 22.0, 24.0, 0.55, 0.45)               # nuit


_PHI_PROFILES = {
    "semaine":  _phi_semaine,
    "mercredi": _phi_mercredi,
    "vacances": _phi_vacances,
    "weekend":  _phi_weekend,
}


def compute_phi(dt: datetime = None) -> float:
    if dt is None:
        dt = datetime.now(LYON_TZ)
    else:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(LYON_TZ)

    t = dt.hour + dt.minute / 60.0
    profile = _PHI_PROFILES[_day_type(dt)]
    return profile(t)


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
    raw = sum(
        BETA[k] * _soft_gate(S[a], THETA[a]) * _soft_gate(S[b], THETA[b])
        for a, b, k in pairs
    )
    return min(raw, 2.0)  # borne empirique — évite surpondération en cas d'explosion simultanée


def compute_alert(risk, anomaly, conv) -> float:
    return LAMBDA["l1"] * risk + LAMBDA["l2"] * anomaly + LAMBDA["l3"] * conv


def compute_spread(zone_id: str, alert_map: dict) -> float:
    nbrs = NEIGHBORS.get(zone_id, [])
    if not nbrs: return 0.0
    K = SPATIAL_KERNEL_DECAY / len(nbrs)
    return sum(K * max(alert_map.get(n, 0.0), 0.0) for n in nbrs)


def compute_urban_score(alert: float, spread: float) -> int:
    raw = alert + LAMBDA["l4"] * spread
    # ── Sémantique du score neutre ──────────────────────────────────────
    # Sigmoid centrée à raw=1.5, PAS à 0. Conséquences :
    #   raw = 0.0 → score ≈ 29  (CALME — tous signaux au baseline)
    #   raw = 1.5 → score = 50  (tension médiane du modèle)
    #   raw = 3.0 → score ≈ 71  (seuil CRITIQUE)
    #
    # Score 50 ≠ "absence de tension". C'est le point d'inflexion où la
    # tension passe de modérée à significative. Le vrai neutre est ~29.
    # Ce choix est intentionnel : il compresse la plage basse (CALME) et
    # étire la plage haute pour mieux différencier TENDU et CRITIQUE.
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
    zone_id: str = None,                         # pour lookup profils horaires
) -> List[dict]:
    """
    Prévision probabiliste sur 30/60/120 min.
    Intègre :
      - phi futur (heures de pointe)
      - tendance récente (delta score / min)
      - profils horaires historiques : projette les signaux bruts à chaque horizon
        en interpolant entre la valeur actuelle et la moyenne historique à cette heure
      - incidents planifiés (starttime/endtime Criter)
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    phi_now = max(compute_phi(dt), 0.1)
    _bl = bl or BASELINE

    # ── Profils horaires historiques ──────────────────────────────────
    hourly_profiles: Dict[int, Dict[str, float]] = {}
    if zone_id:
        try:
            from services.storage import get_hourly_signal_profiles
            day_t = _day_type(dt)
            hourly_profiles = get_hourly_signal_profiles(zone_id, day_type=day_t)
            # Fallback : si pas assez de données pour ce day_type, essayer sans filtre
            if len(hourly_profiles) < 12:
                hourly_profiles = get_hourly_signal_profiles(zone_id)
        except Exception:
            pass  # fallback : forecast classique sans projection

    results = []
    for h in FORECAST_HORIZONS:
        future_dt  = dt + timedelta(minutes=h)
        phi_future = compute_phi(future_dt)
        future_hour = future_dt.hour

        # ── Forecast à 3 scénarios (max wins) ─────────────────────────
        #
        # 1. Persistance décayée : alert × decay × phi_ratio
        #    → modèle classique, bon pour signaux transitoires
        #
        # 2. Situation maintenue + phi futur : recalcule l'alert
        #    avec les mêmes signaux mais phi à l'heure future
        #    → capte : "si les travaux/incidents actuels persistent au rush,
        #              le score monte car φ amplifie"
        #
        # 3. Projection avec incident_schedule Criter :
        #    → utilise le decay par type (travaux=persist, bouchon=decay rapide)
        #    + profils historiques pour les signaux structurels
        #
        # On prend le MAX → le forecast reflète le pire scénario réaliste

        if signals:
            profile_at_h = hourly_profiles.get(future_hour, {})

            # --- 1. Persistance décayée ---
            phi_ratio = min(phi_future / phi_now, 1.8)
            decay = math.exp(-h / 240)
            fa_persist = alert * decay * phi_ratio

            # --- 2. Situation maintenue + phi futur ---
            # Même signaux qu'actuellement, mais phi à l'heure future.
            # "Si rien ne change, quel est le score à 17h ?"
            #
            # Ajustement trafic : si le rush approche (phi_future > phi_now),
            # on interpole le trafic actuel vers mu (congestion moyenne).
            # Criter capte la congestion réelle, mais la projection forward
            # utilise le ratio phi pour anticiper l'intensification.
            maintained_signals = dict(signals)
            if phi_future > phi_now and "traffic" in maintained_signals:
                # Le trafic brut augmente vers la baseline au rush
                # phi_ratio > 1 → on rapproche le trafic de mu (congestion)
                traffic_now = maintained_signals["traffic"]
                traffic_mu = _bl["traffic"]["mu"]
                phi_r = phi_future / phi_now
                # Interpolation vers mu proportionnelle au ratio phi
                # À phi_ratio=1.55 → ~35% vers mu, à phi_ratio=1.0 → 0%
                interp = min(max((phi_r - 1.0) * 0.6, 0.0), 0.5)  # [0, 0.5] — jamais négatif
                maintained_signals["traffic"] = traffic_now + interp * (traffic_mu - traffic_now)

            # Profils historiques : max(actuel, historique) pour transport
            for sig in ("transport",):
                hist_val = profile_at_h.get(sig)
                if hist_val is not None and sig in maintained_signals:
                    maintained_signals[sig] = max(maintained_signals[sig], hist_val)

            risk_future = compute_risk(maintained_signals, phi_future, _bl)
            fa_maintained = (
                LAMBDA["l1"] * risk_future
                + LAMBDA["l2"] * compute_anomaly(maintained_signals, _bl)
                + LAMBDA["l3"] * compute_conv(maintained_signals, _bl)
            )

            # --- 3. Projection avec schedule + profils historiques ---
            fa_proj = 0.0
            if incident_schedule and h in incident_schedule:
                # Le schedule Criter intègre la durée par type :
                #   travaux (type 9) → factor=1.0 (persistent)
                #   bouchon (type 6) → factor décroissant (transitoire)
                proj_signals = dict(signals)
                proj_signals["incident"] = incident_schedule[h]
                # Enrichir avec max(actuel, historique) pour traffic/transport
                for sig in ("traffic", "transport"):
                    hist_val = profile_at_h.get(sig)
                    if hist_val is not None:
                        proj_signals[sig] = max(proj_signals.get(sig, 0), hist_val)

                risk_p  = compute_risk(proj_signals, phi_future, _bl)
                anom_p  = compute_anomaly(proj_signals, _bl)
                conv_p  = compute_conv(proj_signals, _bl)
                fa_proj = compute_alert(risk_p, anom_p, conv_p)

            # --- MAX des 3 scénarios ---
            fa = max(fa_persist, fa_maintained, fa_proj)

            # Tendance récente
            trend_decay   = math.exp(-h / 60)
            trend_contrib = max(-1.0, min(1.0, trend * h * trend_decay))
            fa += trend_contrib * 0.3

            fs = compute_urban_score(fa, spread * math.exp(-h / 240))

        else:
            # Fallback : ancien forecast (decay + phi_ratio) quand pas de profils
            phi_ratio = min(phi_future / phi_now, 1.8)
            decay = math.exp(-h / 240)

            trend_decay   = math.exp(-h / 60)
            trend_contrib = max(-1.0, min(1.0, trend * h * trend_decay))

            fa  = alert * decay * phi_ratio
            fa += trend_contrib * 0.3

            # Remplacement incident planifié
            if signals and incident_schedule and h in incident_schedule:
                incident_now  = signals.get("incident", 0.0)
                z_inc_now     = normalize(incident_now, "incident", _bl)
                inc_alert_now = (
                    LAMBDA["l1"] * phi_now * WEIGHTS["incident"] * z_inc_now
                    + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_now, 0.0)
                )
                z_inc_sched = normalize(incident_schedule[h], "incident", _bl)
                inc_alert_sched = (
                    LAMBDA["l1"] * phi_future * WEIGHTS["incident"] * z_inc_sched
                    + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_sched, 0.0)
                )
                fa = fa - inc_alert_now * decay * phi_ratio + inc_alert_sched

            fs = compute_urban_score(fa, spread * math.exp(-h / 240))

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