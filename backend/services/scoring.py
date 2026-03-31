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
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from zoneinfo import ZoneInfo

LYON_TZ = ZoneInfo("Europe/Paris")

from config import (
    EPSILON, WEIGHTS, LAMBDA, THETA, ALPHA, BETA,
    SPATIAL_KERNEL_DECAY, FORECAST_HORIZONS, FORECAST_HORIZONS_EXTENDED,
    INCIDENT_FORECAST_HALFLIFE_MIN,
)
from services.calendar_utils import day_type as _day_type, load_vacances_from_db
from services.forecast_learning import get_forecast_params

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



BASELINE = {
    "traffic":   {"mu": 1.05, "sigma": 0.15},   # Criter : V≈1.0, O≈2.0, R≈2.8, N≈3.0 — recalibré auto
    "weather":   {"mu": 0.3,  "sigma": 0.35},
    "event":     {"mu": 0.2,  "sigma": 0.3},     # non-stationnaire — exclu de la calibration auto
    "transport": {"mu": 0.50, "sigma": 0.28},
    "incident":  {"mu": 1.70, "sigma": 0.50},
}

# Baselines par zone — surchargent BASELINE si disponibles (calibrées depuis SQLite)
# Structure : zone_id → signal → {mu, sigma}
ZONE_BASELINES: Dict[str, Dict[str, Dict[str, float]]] = {}

# ── Baselines segmentées par créneau horaire ─────────────────────────────────
# Corrige le biais "all-hours" : à 7h10, le trafic (V=1.0) est sous la moyenne
# globale (mu~1.05) qui inclut le rush 8h-9h30. Les z-scores négatifs sont
# amplifiés par φ=1.55, poussant les scores à 21-25 au lieu de ~29.
# Avec des baselines par slot, chaque créneau a son propre mu/sigma.
TIME_SLOTS = [
    ("nuit",   0, 6),    # 00:00 – 05:59
    ("matin",  6, 12),   # 06:00 – 11:59
    ("aprem", 12, 18),   # 12:00 – 17:59
    ("soir",  18, 24),   # 18:00 – 23:59
]

def time_slot(hour: int) -> str:
    """Retourne le créneau horaire pour segmentation des baselines."""
    for name, start, end in TIME_SLOTS:
        if start <= hour < end:
            return name
    return "nuit"

# Structure : slot → signal → {mu, sigma}
BASELINE_BY_SLOT: Dict[str, Dict[str, Dict[str, float]]] = {}
# Structure : zone_id → slot → signal → {mu, sigma}
ZONE_BASELINES_BY_SLOT: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}


def set_baselines(
    global_bl: Dict[str, Dict[str, float]],
    zone_bl: Dict[str, Dict[str, Dict[str, float]]],
) -> None:
    """Met à jour BASELINE et ZONE_BASELINES depuis la calibration.
    Seuls les signaux déjà présents dans BASELINE sont mis à jour."""
    for sig, vals in global_bl.items():
        if sig in BASELINE:
            BASELINE[sig] = vals
    ZONE_BASELINES.clear()
    ZONE_BASELINES.update(zone_bl)


def set_slot_baselines(
    slot_bl: Dict[str, Dict[str, Dict[str, float]]],
    zone_slot_bl: Dict[str, Dict[str, Dict[str, Dict[str, float]]]],
) -> None:
    """Met à jour les baselines segmentées par créneau horaire."""
    BASELINE_BY_SLOT.clear()
    BASELINE_BY_SLOT.update(slot_bl)
    ZONE_BASELINES_BY_SLOT.clear()
    ZONE_BASELINES_BY_SLOT.update(zone_slot_bl)


def _effective_baseline(zone_id: str, dt: datetime = None) -> Dict[str, Dict[str, float]]:
    """Retourne le baseline effectif pour une zone + créneau horaire.
    Fallback : zone+slot → slot global → zone global → BASELINE."""
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hour = dt.astimezone(LYON_TZ).hour
        slot = time_slot(hour)

        # 1. Zone + slot
        zone_slot = ZONE_BASELINES_BY_SLOT.get(zone_id, {}).get(slot)
        if zone_slot:
            return {sig: zone_slot.get(sig, BASELINE[sig]) for sig in BASELINE}

        # 2. Slot global
        slot_bl = BASELINE_BY_SLOT.get(slot)
        if slot_bl:
            return {sig: slot_bl.get(sig, BASELINE[sig]) for sig in BASELINE}

    # 3. Zone global (fallback existant)
    zone_bl = ZONE_BASELINES.get(zone_id, {})
    if zone_bl:
        return {sig: zone_bl.get(sig, BASELINE[sig]) for sig in BASELINE}

    # 4. BASELINE hardcodé
    return BASELINE

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


Z_CAP = 4.0  # z-score max — évite les explosions si sigma est sous-estimé

def normalize(x: float, signal: str, bl: Dict[str, Dict[str, float]] = None) -> float:
    b = (bl or BASELINE)[signal]
    z = (x - b["mu"]) / (b["sigma"] + EPSILON)
    return max(-Z_CAP, min(Z_CAP, z))


def _phi_from_breakpoints(breakpoints: List[tuple], t: float) -> float:
    """Interpole linéairement φ depuis une liste de (heure, valeur) breakpoints."""
    if t <= breakpoints[0][0]:
        return breakpoints[0][1]
    for i in range(1, len(breakpoints)):
        t0, v0 = breakpoints[i - 1]
        t1, v1 = breakpoints[i]
        if t < t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return breakpoints[-1][1]


# ─── Profils φ — breakpoints (heure, valeur) ──────────────────────────────────
# Calibrés sur données réelles Lyon (Criter, CEREMA, EMD 2015).
# Chaque profil est une liste de (t, φ) interpolée linéairement.

# Semaine standard (lun, mar, jeu, ven hors vacances)
# Rush soir > rush matin à Lyon. Pics écoles 11h30 et 16h30.
_BP_SEMAINE = [
    (0.0, 0.50),   # nuit
    (5.0, 0.50),   # fin nuit
    (6.5, 1.00),   # réveil progressif
    (7.0, 1.55),   # montée rush matin
    (9.5, 1.60),   # pic rush matin (8h-9h)
    (10.5, 1.10),  # fin rush matin
    (11.5, 1.10),  # creux matinée
    (12.0, 1.25),  # montée midi (écoles 11h30)
    (13.5, 1.25),  # mini-pic déjeuner
    (14.5, 1.05),  # retour école/bureau
    (16.0, 1.05),  # après-midi calme
    (16.5, 1.40),  # sortie écoles 16h30
    (17.0, 1.75),  # montée rush soir
    (18.0, 1.75),  # pic rush soir (~90%)
    (19.5, 1.30),  # décrue rush soir
    (21.0, 1.00),  # fin rush soir
    (22.5, 0.70),  # soirée → nuit
    (24.0, 0.50),  # nuit profonde
]

# Mercredi hors vacances — pas d'école l'après-midi
# Rush matin identique, rush soir atténué (-15%)
_BP_MERCREDI = [
    (0.0, 0.50),
    (5.0, 0.50),
    (6.5, 1.00),
    (7.0, 1.55),   # rush matin identique
    (9.5, 1.60),
    (10.5, 1.10),
    (11.5, 1.10),
    (12.5, 1.30),  # sortie école matin (12h)
    (13.5, 1.05),  # retour calme
    (16.5, 1.05),  # après-midi calme (pas d'école)
    (17.0, 1.55),  # rush soir commuters seulement
    (18.0, 1.55),  # pic soir atténué (-15%)
    (19.5, 1.20),
    (21.0, 1.00),
    (22.5, 0.70),
    (24.0, 0.50),
]

# Vacances scolaires (jours de semaine)
# Commuters présents, pas d'école → rush atténué (~-20%)
_BP_VACANCES = [
    (0.0, 0.50),
    (5.0, 0.50),
    (6.5, 0.90),
    (7.0, 1.30),   # rush matin allégé
    (9.5, 1.35),   # pic matin -20%
    (10.5, 1.00),
    (12.0, 1.00),  # matinée calme
    (13.5, 1.10),  # midi léger
    (14.5, 1.00),
    (16.5, 1.00),  # après-midi calme
    (17.0, 1.45),  # rush soir allégé
    (18.0, 1.45),  # pic soir -20%
    (19.5, 1.15),
    (21.0, 0.90),
    (22.5, 0.65),
    (24.0, 0.50),
]

# Weekend et jours fériés
# Pas de rush commuter. Pic commercial 10h-18h (Part-Dieu, Confluence).
_BP_WEEKEND = [
    (0.0, 0.45),   # nuit/grasse mat
    (7.0, 0.45),
    (9.0, 0.70),   # réveil lent
    (10.0, 0.90),  # montée shopping
    (12.0, 0.90),  # pic commercial matin
    (13.5, 0.95),  # midi/restau
    (14.5, 0.95),
    (17.0, 1.00),  # pic après-midi
    (18.5, 1.00),  # pic commercial soir
    (20.0, 0.75),  # fermeture commerces
    (22.0, 0.55),  # soirée
    (24.0, 0.45),  # nuit
]

_PHI_PROFILES = {
    "semaine":  _BP_SEMAINE,
    "mercredi": _BP_MERCREDI,
    "vacances": _BP_VACANCES,
    "weekend":  _BP_WEEKEND,
}


def compute_phi(dt: datetime = None) -> float:
    if dt is None:
        dt = datetime.now(LYON_TZ)
    else:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(LYON_TZ)

    t = dt.hour + dt.minute / 60.0
    breakpoints = _PHI_PROFILES[_day_type(dt)]
    return _phi_from_breakpoints(breakpoints, t)


# Signaux pour lesquels un z négatif ne doit pas réduire le risk — clampé à 0.
# weather/event/incident : 0.0 = "pas d'activité" (pas "plus calme que d'habitude").
# traffic/transport : un trafic fluide ou une bonne desserte TCL ne réduit pas la tension.
# Sans ce clamp, les zones structurellement calmes (presquile, fourviere) sont sous-scorées
# car leurs z négatifs sont amplifiés par φ(rush) ≈ 1.6.
_NEUTRAL_WHEN_LOW = frozenset({"weather", "event", "incident", "traffic", "transport"})


def compute_risk(signals: dict, phi: float, bl: Dict = None) -> float:
    total = 0.0
    for s, v in signals.items():
        z = normalize(v, s, bl)
        if s in _NEUTRAL_WHEN_LOW:
            z = max(z, 0.0)
        total += WEIGHTS[s] * z
    return phi * total


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


def _load_hourly_profiles(zone_id: str, day_t: str) -> Dict[int, Dict[str, float]]:
    """Charge les profils horaires historiques depuis la DB. Fallback vide."""
    if not zone_id:
        return {}
    try:
        from services.storage import get_hourly_signal_profiles
        profiles = get_hourly_signal_profiles(zone_id, day_type=day_t)
        if len(profiles) < 12:
            profiles = get_hourly_signal_profiles(zone_id)
        return profiles
    except Exception:
        return {}


def _forecast_short_horizon(
    h: int,
    dt: datetime,
    alert: float,
    spread: float,
    phi_now: float,
    trend: float,
    signals: dict,
    incident_schedule: Dict[int, float],
    bl: Dict,
    hourly_profiles: Dict[int, Dict[str, float]],
) -> dict:
    """
    Forecast pour un horizon court (30/60/120 min).
    3 scénarios max-wins à partir des signaux temps réel.
    """
    future_dt  = dt + timedelta(minutes=h)
    phi_future = compute_phi(future_dt)
    fp         = get_forecast_params()
    decay      = math.exp(-h / fp["decay_halflife_min"])
    phi_ratio  = min(phi_future / phi_now, 1.8)

    if signals:
        profile_at_h = hourly_profiles.get(future_dt.hour, {})

        # 1. Persistance décayée
        fa_persist = alert * decay * phi_ratio

        # 2. Situation maintenue + phi futur
        maintained_signals = dict(signals)
        if phi_future > phi_now and "traffic" in maintained_signals:
            traffic_now = maintained_signals["traffic"]
            traffic_mu = bl["traffic"]["mu"]
            phi_r = phi_future / phi_now
            interp = min(max((phi_r - 1.0) * 0.6, 0.0), 0.5)
            maintained_signals["traffic"] = traffic_now + interp * (traffic_mu - traffic_now)

        for sig in ("transport",):
            hist_val = profile_at_h.get(sig)
            if hist_val is not None and sig in maintained_signals:
                maintained_signals[sig] = max(maintained_signals[sig], hist_val)

        risk_future = compute_risk(maintained_signals, phi_future, bl)
        fa_maintained = (
            LAMBDA["l1"] * risk_future
            + LAMBDA["l2"] * compute_anomaly(maintained_signals, bl)
            + LAMBDA["l3"] * compute_conv(maintained_signals, bl)
        )

        # 3. Projection avec incident_schedule Criter
        fa_proj = 0.0
        if incident_schedule and h in incident_schedule:
            proj_signals = dict(signals)
            proj_signals["incident"] = incident_schedule[h]
            for sig in ("traffic", "transport"):
                hist_val = profile_at_h.get(sig)
                if hist_val is not None:
                    proj_signals[sig] = max(proj_signals.get(sig, 0), hist_val)
            fa_proj = compute_alert(
                compute_risk(proj_signals, phi_future, bl),
                compute_anomaly(proj_signals, bl),
                compute_conv(proj_signals, bl),
            )

        # Moyenne pondérée des scénarios (ADR-012) — weights from forecast_learning
        sw = fp["scenario_weights"]
        sw_np = fp["scenario_weights_no_proj"]
        if fa_proj > 0.0:
            fa_avg = (
                sw.get("persist", 0.25) * fa_persist
                + sw.get("maintained", 0.55) * fa_maintained
                + sw.get("proj", 0.20) * fa_proj
            )
        else:
            fa_avg = sw_np.get("persist", 0.30) * fa_persist + sw_np.get("maintained", 0.70) * fa_maintained
        # Plancher sécuritaire : jamais plus de 30% sous le max
        fa_max = max(fa_persist, fa_maintained, fa_proj)
        fa = max(fa_avg, fa_max * 0.70)

        # Tendance récente
        trend_decay   = math.exp(-h / 60)
        trend_contrib = max(-1.0, min(1.0, trend * h * trend_decay))
        fa += trend_contrib * 0.3

        fs = compute_urban_score(fa, spread * decay)

    else:
        # Fallback : decay + phi_ratio quand pas de signaux
        trend_decay   = math.exp(-h / 60)
        trend_contrib = max(-1.0, min(1.0, trend * h * trend_decay))

        fa  = alert * decay * phi_ratio
        fa += trend_contrib * 0.3

        if signals and incident_schedule and h in incident_schedule:
            incident_now  = signals.get("incident", 0.0)
            z_inc_now     = normalize(incident_now, "incident", bl)
            inc_alert_now = (
                LAMBDA["l1"] * phi_now * WEIGHTS["incident"] * z_inc_now
                + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_now, 0.0)
            )
            z_inc_sched = normalize(incident_schedule[h], "incident", bl)
            inc_alert_sched = (
                LAMBDA["l1"] * phi_future * WEIGHTS["incident"] * z_inc_sched
                + LAMBDA["l2"] * ALPHA["incident"] * max(z_inc_sched, 0.0)
            )
            fa = fa - inc_alert_now * decay * phi_ratio + inc_alert_sched

        fs = compute_urban_score(fa, spread * decay)

    fs = max(0, min(100, fs))
    return {
        "horizon":     f"{h}min" if h <= 60 else f"{h // 60}h",
        "urban_score": fs,
        "level":       score_level(fs),
        "phi":         round(phi_future, 2),
        "confidence":  "high",
    }


def _forecast_extended_horizon(
    h: int,
    dt: datetime,
    zone_id: str,
    bl: Dict,
    incident_schedule: Dict[int, float],
    weather_forecast: Dict[str, float],
) -> dict:
    """
    Forecast pour un horizon étendu (6h/12h/24h).
    Modèle structurel basé sur profils historiques, météo prévue, incidents persistants.
    """
    future_dt   = dt + timedelta(minutes=h)
    phi_future  = compute_phi(future_dt)
    future_hour = future_dt.hour

    # Profils historiques pour le jour futur (peut être un autre day_type)
    ext_profiles = _load_hourly_profiles(zone_id, _day_type(future_dt))
    profile_at_h = ext_profiles.get(future_hour, {})

    # Construire les signaux structurels
    struct_signals: Dict[str, float] = {}
    for sig in ("traffic", "weather", "event", "transport", "incident"):
        struct_signals[sig] = profile_at_h.get(sig, bl[sig]["mu"])

    # Injecter les événements calendrier connus (donnée déterministe)
    from services.events import compute_event_signals
    future_event_signals = compute_event_signals(future_dt.date())
    ev_val = future_event_signals.get(zone_id, 0.0)
    if ev_val > 0:
        struct_signals["event"] = max(struct_signals["event"], ev_val)

    # Météo prévue remplace la moyenne historique (seul signal fiable à 6h+)
    if weather_forecast:
        future_local = future_dt.astimezone(LYON_TZ)
        wf_key = future_local.strftime("%Y-%m-%dT%H:00")
        wf_score = weather_forecast.get(wf_key)
        if wf_score is not None:
            struct_signals["weather"] = wf_score

    # Incidents persistants — décroissance exponentielle (ADR-013)
    # Les incidents se résolvent souvent avant leur endtime déclaré.
    # On blend : historique (rush inclus) + fraction décroissante de l'excès.
    if incident_schedule and h in incident_schedule:
        inc_val = incident_schedule[h]
        if inc_val > 0:
            _inc_halflife = get_forecast_params()["incident_halflife_min"]
            inc_decay = 0.5 ** (h / _inc_halflife)
            hist_inc = struct_signals["incident"]
            struct_signals["incident"] = hist_inc + inc_decay * max(inc_val - hist_inc, 0)

    # L'anomaly est modulée par phi : un incident à 1h du matin
    # a moins d'impact qu'à 8h (personne n'est impacté la nuit).
    risk_ext    = compute_risk(struct_signals, phi_future, bl)
    anomaly_ext = compute_anomaly(struct_signals, bl) * min(phi_future, 1.0)
    conv_ext    = compute_conv(struct_signals, bl)
    fa_ext      = compute_alert(risk_ext, anomaly_ext, conv_ext)

    # Pas de spread à long terme (les voisins évoluent indépendamment)
    fs_ext = max(0, min(100, compute_urban_score(fa_ext, 0.0)))
    conf   = "medium" if h <= 720 else "low"

    return {
        "horizon":     f"{h // 60}h",
        "urban_score": fs_ext,
        "level":       score_level(fs_ext),
        "phi":         round(phi_future, 2),
        "confidence":  conf,
    }


def compute_forecast(
    current_score: int,
    alert: float,
    spread: float,
    dt: datetime = None,
    trend: float = 0.0,
    signals: dict = None,
    incident_schedule: Dict[int, float] = None,
    bl: Dict = None,
    zone_id: str = None,
    weather_forecast: Dict[str, float] = None,
) -> List[dict]:
    """
    Prévision probabiliste sur horizons courts (30/60/120 min) et étendus (6/12/24h).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    phi_now = max(compute_phi(dt), 0.1)
    _bl = bl or BASELINE
    hourly_profiles = _load_hourly_profiles(zone_id, _day_type(dt))

    results = []

    for h in FORECAST_HORIZONS:
        results.append(_forecast_short_horizon(
            h, dt, alert, spread, phi_now, trend,
            signals, incident_schedule, _bl, hourly_profiles,
        ))

    for h in FORECAST_HORIZONS_EXTENDED:
        results.append(_forecast_extended_horizon(
            h, dt, zone_id, _bl, incident_schedule, weather_forecast,
        ))

    return results

def score_zone(zone_id: str, signals: dict, alert_map: dict, dt: datetime = None) -> dict:
    bl      = _effective_baseline(zone_id, dt)
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
        bl      = _effective_baseline(zone_id, dt)
        phi     = compute_phi(dt)
        risk    = compute_risk(signals, phi, bl)
        anomaly = compute_anomaly(signals, bl)
        conv    = compute_conv(signals, bl)
        alert_map[zone_id] = compute_alert(risk, anomaly, conv)
    return [score_zone(z, s, alert_map, dt) for z, s in all_signals.items()]