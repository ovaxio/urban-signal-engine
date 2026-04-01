#!/usr/bin/env python3
"""
Backtest comparatif : nearest-centroid (legacy) vs multi-zone gaussien (ADR-019).

Simule le scoring des 12 zones sous différents scénarios avec chaque mode
d'assignation et compare les scores, niveaux, et distribution des segments.

Usage:
    cd backend && python -m scripts.backtest_multizone

Sortie : tableau comparatif par zone + analyse de sensibilité sigma.
"""

import sys
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    ZONE_CENTROIDS, CRITER_ETAT_TO_RATIO,
    MULTIZONE_SIGMA_KM, MULTIZONE_MIN_WEIGHT,
)
from services.scoring import (
    score_all_zones, BASELINE, ZONE_BASELINES,
    score_level,
)

PARIS = ZoneInfo("Europe/Paris")

# Force global baseline pour résultats reproductibles
ZONE_BASELINES.clear()

# ── Zone assignment functions (standalone, pour A/B) ───────────────────────

_COS_LAT_LYON = math.cos(math.radians(45.76))
_MAX_ZONE_D2 = (2.0 / 111.1) ** 2


def _nearest_zone_legacy(lat: float, lon: float) -> Dict[str, float]:
    """Legacy: winner-takes-all, retourne {zone: 1.0} ou {}."""
    best, best_d = None, float("inf")
    for zone, (zlat, zlon) in ZONE_CENTROIDS.items():
        d = (lat - zlat) ** 2 + ((lon - zlon) * _COS_LAT_LYON) ** 2
        if d < best_d:
            best_d, best = d, zone
    if best_d > _MAX_ZONE_D2:
        return {}
    return {best: 1.0}


def _zone_weights_raw(lat: float, lon: float, sigma_km: float) -> Dict[str, float]:
    """Multi-zone gaussien brut (non normalisé)."""
    _2sigma2 = 2.0 * sigma_km ** 2
    raw: Dict[str, float] = {}
    for zone, (zlat, zlon) in ZONE_CENTROIDS.items():
        d2 = (lat - zlat) ** 2 + ((lon - zlon) * _COS_LAT_LYON) ** 2
        if d2 > _MAX_ZONE_D2:
            continue
        d_km = math.sqrt(d2) * 111.1
        w = math.exp(-(d_km ** 2) / _2sigma2)
        if w >= MULTIZONE_MIN_WEIGHT:
            raw[zone] = w
    return raw


def _zone_weights_distribute(lat: float, lon: float, sigma_km: float) -> Dict[str, float]:
    """Multi-zone sum=1 — pour trafic/vélo'v (segment se distribue)."""
    raw = _zone_weights_raw(lat, lon, sigma_km)
    if not raw:
        return {}
    total = sum(raw.values())
    return {z: round(w / total, 4) for z, w in raw.items()}


def _zone_weights_radiate(lat: float, lon: float, sigma_km: float) -> Dict[str, float]:
    """Multi-zone max=1 — pour incidents (événement rayonne)."""
    raw = _zone_weights_raw(lat, lon, sigma_km)
    if not raw:
        return {}
    max_w = max(raw.values())
    return {z: round(w / max_w, 4) for z, w in raw.items()}


# ── Synthetic traffic data generation ──────────────────────────────────────

# Segments routiers synthétiques réalistes basés sur le réseau lyonnais
# Chaque tuple : (lat, lon, etat_normal, etat_rush)
# etat_rush simule l'heure de pointe 18h
SYNTHETIC_SEGMENTS: List[Tuple[float, float, str, str]] = [
    # Axe Presqu'île - Perrache (Cours de Verdun, pont Kitchener)
    (45.7510, 4.8290, "V", "R"),  # Nord gare Perrache
    (45.7500, 4.8280, "V", "O"),  # Gare Perrache centre
    (45.7495, 4.8295, "V", "R"),  # Cours de Verdun
    (45.7505, 4.8310, "V", "O"),  # Pont Kitchener nord

    # Autoroute A7 / Quais Perrache (rouge sur Google Maps)
    (45.7470, 4.8250, "V", "R"),  # A7 nord confluence
    (45.7460, 4.8240, "V", "N"),  # A7 échangeur Perrache
    (45.7480, 4.8260, "V", "R"),  # Quai Perrache ouest
    (45.7490, 4.8270, "V", "O"),  # Cours Charlemagne nord

    # Presqu'île centre
    (45.7560, 4.8330, "V", "O"),  # Rue de la République
    (45.7550, 4.8325, "V", "V"),  # Bellecour
    (45.7570, 4.8315, "V", "O"),  # Cordeliers

    # Part-Dieu / Brotteaux (rouge vif sur Google Maps)
    (45.7590, 4.8500, "V", "R"),  # Gare Part-Dieu
    (45.7600, 4.8510, "V", "R"),  # Bd Vivier-Merle
    (45.7580, 4.8480, "V", "R"),  # Rue Garibaldi
    (45.7610, 4.8490, "V", "O"),  # Cours Lafayette
    (45.7690, 4.8550, "V", "R"),  # Brotteaux gare
    (45.7685, 4.8560, "V", "R"),  # Bd des Belges
    (45.7700, 4.8540, "V", "O"),  # Tête d'Or sud

    # Guillotière (pont congestionné)
    (45.7465, 4.8420, "V", "R"),  # Pont Guillotière
    (45.7455, 4.8440, "V", "O"),  # Rue de Marseille
    (45.7450, 4.8430, "V", "O"),  # Cours Gambetta

    # Confluence
    (45.7410, 4.8210, "V", "V"),  # Musée Confluences
    (45.7395, 4.8195, "V", "V"),  # Cours Charlemagne sud
    (45.7420, 4.8220, "V", "O"),  # Pont Raymond Barre

    # Vieux-Lyon / Fourvière
    (45.7620, 4.8275, "V", "O"),  # Quai Fulchiron
    (45.7630, 4.8260, "V", "V"),  # Montée du Gourguillon
    (45.7625, 4.8155, "V", "V"),  # Fourvière basilique

    # Croix-Rousse
    (45.7755, 4.8325, "V", "O"),  # Tunnel Croix-Rousse
    (45.7765, 4.8310, "V", "V"),  # Plateau Croix-Rousse

    # Gerland
    (45.7290, 4.8340, "V", "O"),  # Avenue Tony Garnier
    (45.7275, 4.8350, "V", "V"),  # Stade Gerland

    # Montchat / Villette (est)
    (45.7555, 4.8755, "V", "V"),  # Montchat résidentiel
    (45.7565, 4.8770, "V", "O"),  # Avenue Lacassagne
    (45.7725, 4.8615, "V", "O"),  # Villette / Gratte-Ciel
]


def _simulate_traffic(
    segments: List[Tuple[float, float, str, str]],
    rush: bool,
    assign_fn,
) -> Dict[str, float]:
    """Simule fetch_traffic() avec une fonction d'assignation donnée."""
    _CONGESTION_BOOST = 1.5
    _TRAFFIC_NEUTRAL = 1.0

    zone_ratios: Dict[str, list] = {z: [] for z in ZONE_CENTROIDS}

    for lat, lon, etat_calm, etat_rush in segments:
        etat = etat_rush if rush else etat_calm
        ratio = CRITER_ETAT_TO_RATIO.get(etat)
        if ratio is None:
            continue
        weights = assign_fn(lat, lon)
        for z, w in weights.items():
            zone_ratios[z].append((ratio, w))

    result: Dict[str, float] = {}
    for zone, ratios in zone_ratios.items():
        if ratios:
            total_w = sum(w for _, w in ratios)
            avg = sum(r * w for r, w in ratios) / total_w
            n_congested = sum(w for r, w in ratios if r >= 2.0)
            frac = n_congested / total_w
            boosted = avg + frac * _CONGESTION_BOOST
            result[zone] = round(max(0.5, min(3.0, boosted)), 3)
        else:
            result[zone] = _TRAFFIC_NEUTRAL
    return result


def _simulate_incidents(
    assign_fn,
) -> Dict[str, float]:
    """Simule quelques incidents actifs typiques 18h."""
    incidents = [
        # (lat, lon, weight) — basé sur des positions réalistes
        (45.7505, 4.8295, 1.5),   # Accident Cours de Verdun (frontière Perrache/Presqu'île)
        (45.7595, 4.8505, 2.0),   # Bouchon Part-Dieu
        (45.7460, 4.8425, 1.2),   # Incident pont Guillotière
        (45.7695, 4.8555, 1.8),   # Accident Brotteaux
        (45.7415, 4.8215, 0.8),   # Travaux Confluence
    ]

    zone_weights: Dict[str, list] = {z: [] for z in ZONE_CENTROIDS}
    for lat, lon, weight in incidents:
        zones = assign_fn(lat, lon)
        for z, zw in zones.items():
            zone_weights[z].append(weight * zw)

    # Simuler _zone_score_from_weights
    result: Dict[str, float] = {}
    for z, weights in zone_weights.items():
        if not weights:
            result[z] = BASELINE["incident"]["mu"]
        else:
            avg = sum(weights) / len(weights)
            density = 1 + 0.3 * math.log(1 + len(weights))
            result[z] = round(min(avg * density, 3.0), 3)
    return result


def _build_full_signals(
    traffic: Dict[str, float],
    incidents: Dict[str, float],
    rush: bool,
) -> Dict[str, Dict[str, float]]:
    """Construit le dict complet de signaux pour score_all_zones."""
    weather_val = 0.3   # temps normal
    event_val = 0.2     # pas d'événement
    transport_val = 0.55 if rush else 0.45  # légèrement chargé en rush
    return {
        z: {
            "traffic": traffic.get(z, 1.05),
            "weather": weather_val,
            "event": event_val,
            "transport": transport_val,
            "incident": incidents.get(z, BASELINE["incident"]["mu"]),
        }
        for z in ZONE_CENTROIDS
    }


# ── Main comparison ───────────────────────────────────────────────────────

BOUNDARY_ZONES = {"perrache", "presquile", "guillotiere", "confluence"}
LEVELS_ORDER = {"CALME": 0, "MODÉRÉ": 1, "TENDU": 2, "CRITIQUE": 3}


def _compare(label: str, dt: datetime, rush: bool, sigma: float = MULTIZONE_SIGMA_KM):
    """Compare legacy vs multi-zone pour un scénario donné."""
    assign_legacy = _nearest_zone_legacy
    assign_distribute = lambda lat, lon: _zone_weights_distribute(lat, lon, sigma)
    assign_radiate = lambda lat, lon: _zone_weights_radiate(lat, lon, sigma)

    # Traffic — distribute mode (segment se répartit entre zones)
    traffic_legacy = _simulate_traffic(SYNTHETIC_SEGMENTS, rush, assign_legacy)
    traffic_multi = _simulate_traffic(SYNTHETIC_SEGMENTS, rush, assign_distribute)

    # Incidents — radiate mode (événement rayonne sans dilution)
    incidents_legacy = _simulate_incidents(assign_legacy)
    incidents_multi = _simulate_incidents(assign_radiate)

    # Full signals
    signals_legacy = _build_full_signals(traffic_legacy, incidents_legacy, rush)
    signals_multi = _build_full_signals(traffic_multi, incidents_multi, rush)

    # Score
    scores_legacy = {s["zone_id"]: s for s in score_all_zones(signals_legacy, dt)}
    scores_multi = {s["zone_id"]: s for s in score_all_zones(signals_multi, dt)}

    # Segment count per zone
    seg_count_legacy: Dict[str, float] = {z: 0.0 for z in ZONE_CENTROIDS}
    seg_count_multi: Dict[str, float] = {z: 0.0 for z in ZONE_CENTROIDS}
    for lat, lon, _, _ in SYNTHETIC_SEGMENTS:
        for z, w in assign_legacy(lat, lon).items():
            seg_count_legacy[z] += w
        for z, w in assign_distribute(lat, lon).items():
            seg_count_multi[z] += w

    # Display
    print(f"\n{'='*80}")
    print(f"  {label} (sigma={sigma}km)")
    print(f"{'='*80}")
    print(f"{'Zone':15s} {'Legacy':>8s} {'Multi':>8s} {'Delta':>7s} {'Lvl L':>9s} {'Lvl M':>9s} {'Seg L':>6s} {'Seg M':>6s} {'Note':>8s}")
    print("-" * 80)

    regressions = 0
    improvements = 0

    for z in sorted(ZONE_CENTROIDS.keys()):
        sl = scores_legacy[z]
        sm = scores_multi[z]
        delta = sm["urban_score"] - sl["urban_score"]
        is_boundary = z in BOUNDARY_ZONES

        lvl_l = sl["level"]
        lvl_m = sm["level"]
        lvl_change = ""
        if LEVELS_ORDER.get(lvl_m, 0) > LEVELS_ORDER.get(lvl_l, 0):
            lvl_change = "UP"
            if is_boundary:
                improvements += 1
        elif LEVELS_ORDER.get(lvl_m, 0) < LEVELS_ORDER.get(lvl_l, 0):
            lvl_change = "DOWN"
            regressions += 1

        note = ""
        if is_boundary:
            note = "FRONT."
        if abs(delta) >= 5:
            note += " !!!" if delta > 0 else " ---"

        seg_l = seg_count_legacy[z]
        seg_m = seg_count_multi[z]

        print(
            f"  {z:13s} {sl['urban_score']:8d} {sm['urban_score']:8d} "
            f"{delta:+7d} {lvl_l:>9s} {lvl_m:>9s} "
            f"{seg_l:6.1f} {seg_m:6.1f} {note:>8s}"
        )

    print("-" * 80)

    # Traffic signal comparison for boundary zones
    print(f"\n  Signaux traffic bruts (zones frontière) :")
    for z in sorted(BOUNDARY_ZONES):
        tl = traffic_legacy.get(z, 1.05)
        tm = traffic_multi.get(z, 1.05)
        il = incidents_legacy.get(z, 1.70)
        im_ = incidents_multi.get(z, 1.70)
        print(f"    {z:15s}  traffic: {tl:.3f} → {tm:.3f} ({tm-tl:+.3f})  incident: {il:.3f} → {im_:.3f} ({im_-il:+.3f})")

    print(f"\n  Bilan: {improvements} améliorations frontière, {regressions} régressions")
    return scores_legacy, scores_multi


def main():
    print("=" * 80)
    print("  BACKTEST MULTI-ZONE CONTRIBUTION (ADR-019)")
    print("  Comparaison nearest-centroid (legacy) vs gaussien multi-zone")
    print("=" * 80)

    # Scénario 1: Rush 18h (le cas Google Maps)
    dt_rush = datetime(2026, 4, 1, 18, 0, tzinfo=PARIS)
    _compare("Scénario 1 — Rush 18h mardi (cas Google Maps)", dt_rush, rush=True)

    # Scénario 2: Calme 10h (vérifier pas de faux positifs)
    dt_calm = datetime(2026, 4, 1, 10, 0, tzinfo=PARIS)
    _compare("Scénario 2 — Matin calme 10h (baseline)", dt_calm, rush=False)

    # Scénario 3: Rush 18h nuit (faible phi, vérifier proportionnalité)
    dt_night = datetime(2026, 4, 1, 3, 0, tzinfo=PARIS)
    _compare("Scénario 3 — Nuit 3h (phi faible, tous signaux calmes)", dt_night, rush=False)

    # Analyse de sensibilité sigma
    print("\n\n" + "=" * 80)
    print("  ANALYSE DE SENSIBILITÉ — sigma")
    print("=" * 80)

    dt_rush = datetime(2026, 4, 1, 18, 0, tzinfo=PARIS)
    for sigma in [0.8, 1.0, 1.2, 1.5, 2.0]:
        _compare(f"Sensibilité sigma={sigma}km — Rush 18h", dt_rush, rush=True, sigma=sigma)


if __name__ == "__main__":
    main()
