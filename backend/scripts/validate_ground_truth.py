#!/usr/bin/env python3
"""
Ground Truth Validation — Urban Signal Engine
=============================================
Compare le scoring à l'intuition d'expert sur 10 scénarios lyonnais réels.

Objectif : vérifier que le modèle détecte les vraies situations de tension
et reste calme quand il n'y a rien. C'est le test le plus important avant
de vendre le produit à la sécu privée.

Usage:
    cd backend && python -m scripts.validate_ground_truth

Chaque scénario définit :
- des signaux bruts par zone (valeurs réalistes basées sur les sources)
- un datetime fixé (contrôle φ et day_type)
- des attentes d'expert : level_min, level_max, checks sémantiques
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from services.scoring import (
    score_all_zones, compute_phi, BASELINE, ZONE_BASELINES,
    normalize, score_level,
)
from config import ZONE_CENTROIDS

PARIS = ZoneInfo("Europe/Paris")

# ─── Force global baseline pour résultats reproductibles ─────────────────────
# En prod, ZONE_BASELINES est peuplé par calibration auto. Ici on teste
# la cohérence du modèle avec le baseline global uniquement.
ZONE_BASELINES.clear()

LEVELS_ORDER = ["CALME", "MODÉRÉ", "TENDU", "CRITIQUE"]


def _level_idx(level: str) -> int:
    return LEVELS_ORDER.index(level)


# ─── Signaux de référence ────────────────────────────────────────────────────
# Valeurs baseline = "rien de spécial"
NEUTRAL = {
    "traffic": BASELINE["traffic"]["mu"],      # 1.05
    "weather": BASELINE["weather"]["mu"],       # 0.30
    "event": BASELINE["event"]["mu"],           # 0.20
    "transport": BASELINE["transport"]["mu"],   # 0.50
    "incident": BASELINE["incident"]["mu"],     # 1.70
}


@dataclass
class ZoneCheck:
    """Attentes pour une zone dans un scénario."""
    zone_id: str
    level_min: str          # level minimum acceptable (ex: "CALME")
    level_max: str          # level maximum acceptable (ex: "MODÉRÉ")
    must_not_be: str = ""   # hard constraint: "TENDU" = ne doit JAMAIS être TENDU ou plus
    top_cause: str = ""     # signal attendu dans top_causes (ex: "incident")


@dataclass
class Scenario:
    """Scénario de validation ground truth."""
    name: str
    context: str            # pourquoi ce scénario est important pour la sécu privée
    dt: datetime
    overrides: Dict[str, Dict[str, float]]  # zone_id → {signal: value}
    checks: List[ZoneCheck]
    check_spread_from: str = ""   # zone source de spread
    check_spread_to: str = ""     # zone qui doit recevoir du spread


def _build_signals(overrides: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """12 zones à baseline, avec overrides pour certaines."""
    return {
        zone: {**NEUTRAL, **overrides.get(zone, {})}
        for zone in ZONE_CENTROIDS
    }


# ─── 10 Scénarios ────────────────────────────────────────────────────────────

SCENARIOS: List[Scenario] = [

    # ── 1. CALME ABSOLU — nuit profonde ──────────────────────────────────────
    Scenario(
        name="1. Nuit calme mardi 3h",
        context="Si le modèle score > 30 la nuit sans aucun signal, il génère du bruit inutile.",
        dt=datetime(2026, 3, 24, 3, 0, tzinfo=PARIS),
        overrides={
            z: {"traffic": 0.6, "weather": 0.1, "event": 0.0, "transport": 0.2, "incident": 0.5}
            for z in ZONE_CENTROIDS
        },
        checks=[
            ZoneCheck("part-dieu", "CALME", "CALME", must_not_be="MODÉRÉ"),
            ZoneCheck("presquile", "CALME", "CALME", must_not_be="MODÉRÉ"),
            ZoneCheck("gerland",   "CALME", "CALME", must_not_be="MODÉRÉ"),
        ],
    ),

    # ── 2. RUSH NORMAL — le rush quotidien n'est PAS de la tension ──────────
    Scenario(
        name="2. Rush lundi 8h30 normal",
        context="Un rush standard ne doit pas déclencher d'alerte. Si oui, le client ignore le système.",
        dt=datetime(2026, 3, 23, 8, 30, tzinfo=PARIS),
        overrides={
            # Traffic légèrement au-dessus du baseline (z ≈ 1.0)
            "part-dieu": {"traffic": 1.20, "incident": 1.70, "transport": 0.52},
            "presquile": {"traffic": 1.15, "incident": 1.70, "transport": 0.50},
            "perrache":  {"traffic": 1.18, "incident": 1.65, "transport": 0.52},
        },
        checks=[
            ZoneCheck("part-dieu", "CALME", "MODÉRÉ", must_not_be="TENDU"),
            ZoneCheck("presquile", "CALME", "MODÉRÉ", must_not_be="TENDU"),
            ZoneCheck("gerland",   "CALME", "CALME"),  # pas de surcharge ici
        ],
    ),

    # ── 3. MATCH OL — la sécu privée DOIT être alertée ──────────────────────
    Scenario(
        name="3. Match OL vendredi 20h — Gerland",
        context="Scénario typique client sécu événementielle. Gerland doit être en tension forte.",
        dt=datetime(2026, 3, 27, 20, 0, tzinfo=PARIS),
        overrides={
            "gerland": {
                "traffic": 2.0,      # O — dense autour du stade
                "incident": 2.3,     # déviations + afflux piétons
                "transport": 0.80,   # métro B bondé, vélov pris
                "event": 2.5,        # match OL
                "weather": 0.30,     # météo neutre
            },
            "perrache": {
                "traffic": 1.5,      # report depuis Gerland
                "incident": 1.8,
                "transport": 0.60,
            },
            "guillotiere": {
                "traffic": 1.4,
                "incident": 1.8,
                "transport": 0.55,
            },
        },
        checks=[
            ZoneCheck("gerland",     "TENDU", "CRITIQUE", top_cause="event"),
            ZoneCheck("perrache",    "MODÉRÉ", "TENDU"),   # voisin direct
            ZoneCheck("croix-rousse", "CALME", "CALME"),   # loin du stade
        ],
        check_spread_from="gerland",
        check_spread_to="perrache",
    ),

    # ── 4. ORAGE + RUSH — convergence météo/trafic ──────────────────────────
    Scenario(
        name="4. Orage violent rush soir lundi 18h",
        context="Convergence trafic+météo+incidents = vrai signal de tension opérationnelle.",
        dt=datetime(2026, 3, 23, 18, 0, tzinfo=PARIS),
        overrides={
            z: {
                "traffic": 1.8,      # embouteillages (pluie)
                "weather": 2.5,      # orage
                "incident": 2.3,     # accrochages
                "transport": 0.70,   # perturbé
                "event": 0.0,
            }
            for z in ["part-dieu", "presquile", "perrache", "guillotiere"]
        },
        checks=[
            ZoneCheck("part-dieu",  "TENDU", "CRITIQUE"),
            ZoneCheck("presquile",  "TENDU", "CRITIQUE"),
            ZoneCheck("fourviere",  "CALME", "MODÉRÉ"),    # pas impacté directement
        ],
    ),

    # ── 5. ACCIDENT TUNNEL FOURVIÈRE — incident majeur localisé ──────────────
    Scenario(
        name="5. Accident tunnel Fourvière lundi 17h",
        context="Tunnel fermé = cascade sur Vieux-Lyon et Presqu'île. Test du spread spatial.",
        dt=datetime(2026, 3, 23, 17, 0, tzinfo=PARIS),
        overrides={
            "fourviere": {
                "traffic": 2.8,      # R → quasi bloqué
                "incident": 3.0,     # accident majeur
                "transport": 0.75,   # bus déviés
            },
            "vieux-lyon": {
                "traffic": 1.35,     # report modéré (z ≈ 2.0)
                "incident": 1.85,
                "transport": 0.55,
            },
            "presquile": {
                "traffic": 1.25,     # léger report (z ≈ 1.3)
                "incident": 1.80,
            },
        },
        checks=[
            ZoneCheck("fourviere",  "TENDU", "CRITIQUE", top_cause="incident"),
            ZoneCheck("vieux-lyon", "MODÉRÉ", "CRITIQUE"),  # report + spread → TENDU plausible
            ZoneCheck("montchat",   "CALME", "CALME"),     # loin
        ],
        check_spread_from="fourviere",
        check_spread_to="vieux-lyon",
    ),

    # ── 6. DIMANCHE MATIN CALME ─────────────────────────────────────────────
    Scenario(
        name="6. Dimanche matin 9h — calme",
        context="Le weekend sans événement doit être silencieux. Sinon c'est du bruit.",
        dt=datetime(2026, 3, 29, 9, 0, tzinfo=PARIS),
        overrides={
            z: {"traffic": 0.8, "weather": 0.15, "event": 0.0, "transport": 0.30, "incident": 1.0}
            for z in ZONE_CENTROIDS
        },
        checks=[
            ZoneCheck("part-dieu",  "CALME", "CALME", must_not_be="MODÉRÉ"),
            ZoneCheck("presquile",  "CALME", "CALME", must_not_be="MODÉRÉ"),
            ZoneCheck("confluence", "CALME", "CALME", must_not_be="MODÉRÉ"),
        ],
    ),

    # ── 7. SIGNAL ISOLÉ — un seul signal élevé ne suffit PAS ────────────────
    Scenario(
        name="7. Météo seule élevée, reste normal — mardi 14h",
        context="Forte pluie sans impact trafic = pas de tension opérationnelle. Test anti-faux-positif.",
        dt=datetime(2026, 3, 24, 14, 0, tzinfo=PARIS),
        overrides={
            z: {"weather": 2.0, "traffic": 1.05, "incident": 1.70, "transport": 0.50, "event": 0.0}
            for z in ZONE_CENTROIDS
        },
        checks=[
            ZoneCheck("part-dieu",  "CALME", "MODÉRÉ", must_not_be="TENDU"),
            ZoneCheck("presquile",  "CALME", "MODÉRÉ", must_not_be="TENDU"),
        ],
    ),

    # ── 8. VACANCES SCOLAIRES — rush atténué ────────────────────────────────
    Scenario(
        name="8. Vacances scolaires mardi 8h30",
        context="Même trafic en vacances = score plus bas (phi atténué). Vérifie le profil temporel.",
        dt=datetime(2026, 4, 7, 8, 30, tzinfo=PARIS),  # vacances printemps Zone A
        overrides={
            "part-dieu": {"traffic": 1.20, "incident": 1.70, "transport": 0.52},
        },
        checks=[
            # Même signaux que scénario 2 mais phi vacances < phi semaine
            ZoneCheck("part-dieu", "CALME", "MODÉRÉ", must_not_be="TENDU"),
        ],
    ),

    # ── 9. CONVERGENCE TOTALE — tous signaux au max ─────────────────────────
    Scenario(
        name="9. Convergence totale Part-Dieu jeudi 18h",
        context="Pire cas réaliste. Le score DOIT être CRITIQUE pour crédibiliser les alertes.",
        dt=datetime(2026, 3, 26, 18, 0, tzinfo=PARIS),
        overrides={
            "part-dieu": {
                "traffic": 2.5,      # entre R et N
                "incident": 3.0,     # accidents multiples
                "transport": 0.95,   # TC à l'arrêt
                "weather": 2.5,      # orage
                "event": 2.0,        # salon en cours
            },
        },
        checks=[
            ZoneCheck("part-dieu", "CRITIQUE", "CRITIQUE"),
        ],
    ),

    # ── 10. MANIFESTATION PRESQU'ÎLE — cas d'usage sécu privée ──────────────
    Scenario(
        name="10. Manifestation Presqu'île mardi 14h",
        context="Cortège Bellecour→Terreaux. Le client sécu doit voir TENDU sur Presqu'île.",
        dt=datetime(2026, 3, 24, 14, 0, tzinfo=PARIS),
        overrides={
            "presquile": {
                "traffic": 2.0,      # fermetures de rues
                "incident": 2.5,     # manifestation signalée
                "transport": 0.75,   # bus déviés
                "event": 1.5,        # event public
            },
            "guillotiere": {
                "traffic": 1.20,     # léger report (z ≈ 1.0)
                "incident": 1.75,    # quasi baseline
            },
            "vieux-lyon": {
                "traffic": 1.15,
                "incident": 1.75,
            },
        },
        checks=[
            ZoneCheck("presquile",   "TENDU", "CRITIQUE", top_cause="incident"),
            ZoneCheck("guillotiere", "CALME", "MODÉRÉ"),
            ZoneCheck("montchat",    "CALME", "CALME"),     # loin
        ],
    ),
]


# ─── Exécution ────────────────────────────────────────────────────────────────

def _check_result(check: ZoneCheck, result: dict) -> List[str]:
    """Vérifie un résultat contre les attentes. Retourne les erreurs."""
    errors = []
    score = result["urban_score"]
    level = result["level"]

    # Vérification level dans la plage acceptable
    idx = _level_idx(level)
    idx_min = _level_idx(check.level_min)
    idx_max = _level_idx(check.level_max)

    if idx < idx_min or idx > idx_max:
        errors.append(
            f"  {check.zone_id}: level={level} (score={score})"
            f" — attendu entre {check.level_min} et {check.level_max}"
        )

    # Hard constraint: must_not_be
    if check.must_not_be:
        idx_forbidden = _level_idx(check.must_not_be)
        if idx >= idx_forbidden:
            errors.append(
                f"  {check.zone_id}: level={level} (score={score})"
                f" — NE DOIT PAS être {check.must_not_be} ou plus"
            )

    # Top cause check
    if check.top_cause:
        label_map = {
            "traffic": "Trafic", "weather": "Météo", "event": "Événement",
            "transport": "Transport", "incident": "Incidents",
        }
        label = label_map.get(check.top_cause, check.top_cause)
        causes_str = " ".join(result.get("top_causes", []))
        if label not in causes_str:
            errors.append(
                f"  {check.zone_id}: '{check.top_cause}' absent des top_causes"
                f" → {result.get('top_causes', [])}"
            )

    return errors


def run_scenario(scenario: Scenario) -> tuple:
    """Exécute un scénario. Retourne (errors, results)."""
    signals = _build_signals(scenario.overrides)
    results = score_all_zones(signals, scenario.dt)
    result_map = {r["zone_id"]: r for r in results}
    errors = []

    for check in scenario.checks:
        r = result_map.get(check.zone_id)
        if not r:
            errors.append(f"  {check.zone_id}: zone introuvable")
            continue
        errors.extend(_check_result(check, r))

    # Spread check
    if scenario.check_spread_from and scenario.check_spread_to:
        target = result_map.get(scenario.check_spread_to, {})
        spread_val = target.get("components", {}).get("spread", 0)
        source = result_map.get(scenario.check_spread_from, {})
        source_alert = source.get("alert", 0)
        if source_alert > 0.5 and spread_val <= 0.001:
            errors.append(
                f"  spread: {scenario.check_spread_to} devrait recevoir du spread"
                f" de {scenario.check_spread_from} (alert source={source_alert:.2f})"
            )

    return errors, result_map


def main():
    print("=" * 72)
    print("  GROUND TRUTH VALIDATION — Urban Signal Engine")
    print("  Baseline global (pas de calibration zone-specific)")
    print("=" * 72)
    print()

    total_pass = 0
    total_fail = 0
    findings = []

    for scenario in SCENARIOS:
        phi = compute_phi(scenario.dt)
        errors, result_map = run_scenario(scenario)

        status = "\033[32m✓ PASS\033[0m" if not errors else "\033[31m✗ FAIL\033[0m"
        if not errors:
            total_pass += 1
        else:
            total_fail += 1

        print(f"  {status}  {scenario.name}")
        print(f"         φ={phi:.2f} | {scenario.context}")

        # Détail des zones vérifiées
        for check in scenario.checks:
            r = result_map.get(check.zone_id, {})
            score = r.get("urban_score", "?")
            level = r.get("level", "?")
            comps = r.get("components", {})
            causes = r.get("top_causes", [])

            # Marqueur visuel
            idx = _level_idx(level) if level in LEVELS_ORDER else -1
            idx_min = _level_idx(check.level_min)
            idx_max = _level_idx(check.level_max)
            in_range = idx_min <= idx <= idx_max
            marker = "✓" if in_range else "✗"

            print(
                f"         {marker} {check.zone_id:15s} score={score:3d} {level:8s}"
                f"  risk={comps.get('risk', 0):+.2f}"
                f" anom={comps.get('anomaly', 0):.2f}"
                f" conv={comps.get('conv', 0):.2f}"
                f" sprd={comps.get('spread', 0):.2f}"
                f"  {causes}"
            )

        if errors:
            for e in errors:
                print(f"\033[33m         ⚠  {e}\033[0m")
            findings.append((scenario.name, errors))

        print()

    # ─── Résumé ──────────────────────────────────────────────────────────────
    print("=" * 72)
    total = total_pass + total_fail
    if total_fail == 0:
        print(f"\033[32m  RÉSULTAT: {total_pass}/{total} scénarios validés ✓\033[0m")
        print("  Le modèle est cohérent avec l'intuition d'expert.")
    else:
        print(f"\033[31m  RÉSULTAT: {total_pass}/{total} validés — {total_fail} en échec\033[0m")
        print()
        print("  FINDINGS:")
        for name, errs in findings:
            print(f"    {name}")
            for e in errs:
                print(f"      {e}")
    print("=" * 72)

    # ─── Diagnostic sensibilité baseline ─────────────────────────────────────
    print()
    print("  DIAGNOSTIC — Sensibilité du baseline global")
    print("  " + "-" * 50)
    for sig in BASELINE:
        b = BASELINE[sig]
        z1 = b["mu"] + b["sigma"]  # +1σ
        z2 = b["mu"] + 2 * b["sigma"]  # +2σ
        z4 = b["mu"] + 4 * b["sigma"]  # cap
        print(
            f"  {sig:12s}  μ={b['mu']:.2f}  σ={b['sigma']:.2f}"
            f"  | +1σ={z1:.2f}  +2σ={z2:.2f}  cap(4σ)={z4:.2f}"
        )
    print()
    print("  NOTE: Un σ très serré (ex: traffic σ=0.15) rend le modèle")
    print("  très sensible aux petites variations. La calibration par zone")
    print("  (ZONE_BASELINES) atténue cet effet en production.")
    print()

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
