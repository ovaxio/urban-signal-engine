#!/usr/bin/env python3
"""
Urban Score Engine — Model Risk Validation
===========================================
Validates the mathematical robustness of the scoring model against historical
data stored in SQLite.

Read-only: no writes to DB, no modifications to existing files.
Standalone: stdlib Python only + config.py (local module).

Usage:
    cd backend/
    python validate_model_risk.py --db data/urban_signals.db [--limit 5000] [--phase 0]
"""

import argparse
import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from config import WEIGHTS, LAMBDA, THETA, ALPHA, BETA, EPSILON, SPATIAL_KERNEL_DECAY

PARIS_TZ = ZoneInfo("Europe/Paris")

# ─── Scoring constants (from scoring.py — standalone copy) ───────────────────
# These are the DEFAULT baselines; calibration_snapshot.json overrides at runtime.
BASELINE_DEFAULTS = {
    "traffic":   {"mu": 1.05, "sigma": 0.15},
    "weather":   {"mu": 0.3,  "sigma": 0.35},
    "event":     {"mu": 0.2,  "sigma": 0.3},
    "transport": {"mu": 0.50, "sigma": 0.28},
    "incident":  {"mu": 1.70, "sigma": 0.50},
}

Z_CAP = 4.0
SIGNALS = list(WEIGHTS.keys())
NEUTRAL_WHEN_LOW = frozenset(SIGNALS)  # All 5 signals — z clamped >= 0 in risk (ADR-010)

CONV_PAIRS = [
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

NEIGHBORS = {
    "part-dieu":    ["brotteaux", "villette", "montchat", "guillotiere"],
    "presquile":    ["part-dieu", "vieux-lyon", "perrache", "guillotiere"],
    "vieux-lyon":   ["presquile", "perrache", "fourviere"],
    "perrache":     ["presquile", "vieux-lyon", "gerland", "confluence"],
    "gerland":      ["perrache", "guillotiere"],
    "guillotiere":  ["presquile", "part-dieu", "gerland"],
    "brotteaux":    ["part-dieu", "villette"],
    "villette":     ["brotteaux", "part-dieu", "montchat"],
    "montchat":     ["part-dieu", "villette"],
    "fourviere":    ["vieux-lyon", "presquile"],
    "croix-rousse": ["presquile", "brotteaux"],
    "confluence":   ["perrache", "vieux-lyon"],
}

TIME_SLOTS = [("nuit", 0, 6), ("matin", 6, 12), ("aprem", 12, 18), ("soir", 18, 24)]


def _time_slot(hour: int) -> str:
    for name, start, end in TIME_SLOTS:
        if start <= hour < end:
            return name
    return "nuit"


# ─── Scoring functions (standalone reimplementation) ─────────────────────────

def normalize(x: float, signal: str, bl: dict = None) -> float:
    b = (bl or BASELINE_DEFAULTS)[signal]
    z = (x - b["mu"]) / (b["sigma"] + EPSILON)
    return max(-Z_CAP, min(Z_CAP, z))


def soft_gate(z: float, theta: float, k: float = 4.0) -> float:
    return 1.0 / (1.0 + math.exp(-k * (z - theta)))


def compute_risk(raw_signals: dict, phi: float, bl: dict = None) -> float:
    total = 0.0
    for s, v in raw_signals.items():
        z = normalize(v, s, bl)
        if s in NEUTRAL_WHEN_LOW:
            z = max(z, 0.0)
        total += WEIGHTS[s] * z
    return phi * total


def compute_anomaly(raw_signals: dict, bl: dict = None) -> float:
    return sum(ALPHA[s] * max(normalize(v, s, bl), 0.0) for s, v in raw_signals.items())


def compute_conv(raw_signals: dict, bl: dict = None) -> float:
    S = {s: normalize(v, s, bl) for s, v in raw_signals.items()}
    raw = sum(
        BETA[k] * soft_gate(S[a], THETA[a]) * soft_gate(S[b], THETA[b])
        for a, b, k in CONV_PAIRS
    )
    return min(raw, 2.0)


def compute_alert(risk: float, anomaly: float, conv: float) -> float:
    return LAMBDA["l1"] * risk + LAMBDA["l2"] * anomaly + LAMBDA["l3"] * conv


def compute_spread(zone_id: str, alert_map: dict) -> float:
    nbrs = NEIGHBORS.get(zone_id, [])
    if not nbrs:
        return 0.0
    K = SPATIAL_KERNEL_DECAY / len(nbrs)
    return sum(K * max(alert_map.get(n, 0.0), 0.0) for n in nbrs)


def compute_urban_score(alert: float, spread: float = 0.0) -> int:
    # score≈29 quand alert+λ₄·spread=0 — régime neutre (signaux au baseline).
    # score=50 quand alert+λ₄·spread=1.5 — tension médiane du modèle.
    # Sigmoid centrée à raw=1.5 avec k=0.6.
    raw = alert + LAMBDA["l4"] * spread
    normalized = 1.0 / (1.0 + math.exp(-0.6 * (raw - 1.5)))
    return int(max(0, min(100, normalized * 100)))


def compute_from_z_scores(z_scores: dict, phi: float = 1.0) -> Tuple[int, dict]:
    """Compute score directly from z-scores (Phase 0 neutral test)."""
    risk_total = 0.0
    for s in SIGNALS:
        z = z_scores.get(s, 0.0)
        if s in NEUTRAL_WHEN_LOW:
            z = max(z, 0.0)
        risk_total += WEIGHTS[s] * z
    risk = phi * risk_total
    anomaly = sum(ALPHA[s] * max(z_scores.get(s, 0.0), 0.0) for s in SIGNALS)
    conv_raw = sum(
        BETA[k] * soft_gate(z_scores.get(a, 0.0), THETA[a])
               * soft_gate(z_scores.get(b, 0.0), THETA[b])
        for a, b, k in CONV_PAIRS
    )
    conv = min(conv_raw, 2.0)
    alert = compute_alert(risk, anomaly, conv)
    score = compute_urban_score(alert)
    return score, {"risk": risk, "anomaly": anomaly, "conv": conv, "conv_raw": conv_raw, "alert": alert}


# ─── Phi reconstruction ─────────────────────────────────────────────────────
# Breakpoints from scoring.py — profiles φ(t) par type de jour

_BP_SEMAINE = [
    (0.0, 0.50), (5.0, 0.50), (6.5, 1.00), (7.0, 1.55), (9.5, 1.60),
    (10.5, 1.10), (11.5, 1.10), (12.0, 1.25), (13.5, 1.25), (14.5, 1.05),
    (16.0, 1.05), (16.5, 1.40), (17.0, 1.75), (18.0, 1.75), (19.5, 1.30),
    (21.0, 1.00), (22.5, 0.70), (24.0, 0.50),
]
_BP_MERCREDI = [
    (0.0, 0.50), (5.0, 0.50), (6.5, 1.00), (7.0, 1.55), (9.5, 1.60),
    (10.5, 1.10), (11.5, 1.10), (12.5, 1.30), (13.5, 1.05), (16.5, 1.05),
    (17.0, 1.55), (18.0, 1.55), (19.5, 1.20), (21.0, 1.00), (22.5, 0.70),
    (24.0, 0.50),
]
_BP_VACANCES = [
    (0.0, 0.50), (5.0, 0.50), (6.5, 0.90), (7.0, 1.30), (9.5, 1.35),
    (10.5, 1.00), (12.0, 1.00), (13.5, 1.10), (14.5, 1.00), (16.5, 1.00),
    (17.0, 1.45), (18.0, 1.45), (19.5, 1.15), (21.0, 0.90), (22.5, 0.65),
    (24.0, 0.50),
]
_BP_WEEKEND = [
    (0.0, 0.45), (7.0, 0.45), (9.0, 0.70), (10.0, 0.90), (12.0, 0.90),
    (13.5, 0.95), (14.5, 0.95), (17.0, 1.00), (18.5, 1.00), (20.0, 0.75),
    (22.0, 0.55), (24.0, 0.45),
]
_PHI_PROFILES = {
    "semaine": _BP_SEMAINE, "mercredi": _BP_MERCREDI,
    "vacances": _BP_VACANCES, "weekend": _BP_WEEKEND,
}


def _phi_from_breakpoints(breakpoints: list, t: float) -> float:
    if t <= breakpoints[0][0]:
        return breakpoints[0][1]
    for i in range(1, len(breakpoints)):
        t0, v0 = breakpoints[i - 1]
        t1, v1 = breakpoints[i]
        if t < t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return breakpoints[-1][1]


def _easter(year: int) -> date:
    """Calcul de Pâques — algorithme de Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month, day = divmod(h + el - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _jours_feries(year: int) -> set:
    fixed = {date(year, m, d) for m, d in
             [(1, 1), (5, 1), (5, 8), (7, 14), (8, 15), (11, 1), (11, 11), (12, 25)]}
    e = _easter(year)
    mobile = {e + timedelta(days=1), e + timedelta(days=39), e + timedelta(days=50)}
    return fixed | mobile


# Fallback vacances scolaires Zone A (Lyon)
_FALLBACK_VACANCES = [
    (date(2025, 10, 18), date(2025, 11, 3)),
    (date(2025, 12, 20), date(2026, 1, 5)),
    (date(2026, 2, 7),   date(2026, 2, 23)),
    (date(2026, 4, 4),   date(2026, 4, 20)),
    (date(2026, 7, 4),   date(2026, 9, 1)),
    (date(2026, 10, 17), date(2026, 11, 2)),
    (date(2026, 12, 19), date(2027, 1, 4)),
]


def _load_vacances(db_path: Optional[Path]) -> List[Tuple[date, date]]:
    if db_path and db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute("SELECT start_date, end_date FROM calendar_vacances").fetchall()
            conn.close()
            if rows:
                return [(date.fromisoformat(r[0]), date.fromisoformat(r[1])) for r in rows]
        except Exception:
            pass
    return list(_FALLBACK_VACANCES)


def _day_type(d: date, vacances: list, holidays: set) -> str:
    if d.weekday() in (5, 6) or d in holidays:
        return "weekend"
    for start, end in vacances:
        if start <= d <= end:
            return "vacances"
    if d.weekday() == 2:
        return "mercredi"
    return "semaine"


def reconstruct_phi(ts_str: str, vacances: list, holidays: set) -> float:
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        paris = dt.astimezone(PARIS_TZ)
        t = paris.hour + paris.minute / 60.0
        dtype = _day_type(paris.date(), vacances, holidays)
        return _phi_from_breakpoints(_PHI_PROFILES[dtype], t)
    except Exception:
        return 1.0


# ─── Calibration snapshot loader ─────────────────────────────────────────────

def _load_calibration(db_path: Optional[Path]) -> Tuple[dict, dict, dict, dict]:
    """Load calibration_snapshot.json if available alongside the DB.
    Returns (global_bl, zone_bl, slot_bl, zone_slot_bl)."""
    snapshot_path = None
    if db_path:
        snapshot_path = db_path.parent / "calibration_snapshot.json"
    if not snapshot_path or not snapshot_path.exists():
        return BASELINE_DEFAULTS, {}, {}, {}

    try:
        with open(snapshot_path) as f:
            snap = json.load(f)
    except Exception:
        return BASELINE_DEFAULTS, {}, {}, {}

    # Merge with defaults (event is excluded from calibration, keep default)
    global_bl = dict(BASELINE_DEFAULTS)
    for sig, vals in snap.get("baseline", {}).items():
        if sig in global_bl:
            global_bl[sig] = vals

    zone_bl = snap.get("zone_baselines", {})
    slot_bl = snap.get("baseline_by_slot", {})
    zone_slot_bl = snap.get("zone_baselines_by_slot", {})
    return global_bl, zone_bl, slot_bl, zone_slot_bl


def effective_baseline(
    zone_id: str,
    hour: int,
    global_bl: dict,
    zone_bl: dict,
    slot_bl: dict,
    zone_slot_bl: dict,
) -> dict:
    """Reproduce scoring.py _effective_baseline fallback chain."""
    slot = _time_slot(hour)

    # 1. Zone + slot
    zs = zone_slot_bl.get(zone_id, {}).get(slot)
    if zs:
        return {sig: zs.get(sig, global_bl.get(sig, BASELINE_DEFAULTS[sig])) for sig in BASELINE_DEFAULTS}

    # 2. Slot global
    sl = slot_bl.get(slot)
    if sl:
        return {sig: sl.get(sig, global_bl.get(sig, BASELINE_DEFAULTS[sig])) for sig in BASELINE_DEFAULTS}

    # 3. Zone global
    zb = zone_bl.get(zone_id)
    if zb:
        return {sig: zb.get(sig, global_bl.get(sig, BASELINE_DEFAULTS[sig])) for sig in BASELINE_DEFAULTS}

    # 4. Global baseline
    return global_bl


# ─── DB helpers ──────────────────────────────────────────────────────────────

def load_history(db_path: Path, limit: int) -> List[dict]:
    """Load most recent rows from signals_history (live preferred, seed fallback)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Try live data first
    count = conn.execute(
        "SELECT COUNT(*) FROM signals_history WHERE source = 'live' AND raw_traffic IS NOT NULL"
    ).fetchone()[0]

    if count > 0:
        source_filter = "source = 'live' AND"
        source_label = "live"
    else:
        source_filter = ""
        source_label = "seed (no live data)"

    rows = conn.execute(f"""
        SELECT ts, zone_id, urban_score,
               raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
               traffic, weather, event, transport
        FROM signals_history
        WHERE {source_filter} raw_traffic IS NOT NULL
        ORDER BY ts DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()
    return [dict(r) for r in rows], source_label


# ═════════════════════════════════════════════════════════════════════════════
# Phase 0 — Neutral Regime Test
# ═════════════════════════════════════════════════════════════════════════════

def phase_0() -> bool:
    print("\n=== Phase 0 — Neutral Regime ===")

    z_scores = {s: 0.0 for s in SIGNALS}
    score, components = compute_from_z_scores(z_scores, phi=1.0)

    # Theoretical score at raw=0: sigmoid(-0.6 * 1.5) = 1/(1+exp(0.9))
    theoretical = 1.0 / (1.0 + math.exp(0.9)) * 100
    deviation = abs(score - theoretical)
    conv_residual = components["conv_raw"]

    print(f"  All z=0, phi=1.0, spread=0 → score = {score}")
    print(f"  Theoretical sigmoid(0) = {theoretical:.2f}")
    print(f"  Deviation from theoretical: {deviation:.2f} pts")
    print(f"  Conv residual at z=0 : {conv_residual:.6f}  (target: < 0.10)")
    print(f"  Components: risk={components['risk']:.6f}, anomaly={components['anomaly']:.6f}, "
          f"conv={components['conv']:.6f}")
    print()
    print(f"  Note: score≈29 at z=0 is BY DESIGN — sigmoid centered at raw=1.5,")
    print(f"  so neutral (all signals at baseline) = CALME, not MODERE.")

    if conv_residual >= 0.10:
        print(f"  ❌  Conv residual {conv_residual:.4f} >= 0.10 — θ values too low")
        return False
    elif deviation <= 2:
        print(f"  ✅  Neutral regime coherent (deviation {deviation:.2f} ≤ 2pt)")
        return True
    elif deviation <= 5:
        print(f"  ⚠️  Minor deviation ({deviation:.2f} ≤ 5pt) — conv residual may be accumulating")
        return True
    else:
        print(f"  ❌  Deviation {deviation:.2f} > 5pt — model neutral point is off")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Phase 1 — Baseline Replay
# ═════════════════════════════════════════════════════════════════════════════

def _score_from_z(z_scores: dict, phi: float) -> Tuple[int, float]:
    """Compute score from z-scores directly. Returns (score, alert)."""
    risk = phi * sum(WEIGHTS[s] * max(z_scores.get(s, 0.0), 0.0) for s in SIGNALS)
    anomaly = sum(ALPHA[s] * max(z_scores.get(s, 0.0), 0.0) for s in SIGNALS)
    conv_raw = sum(
        BETA[k] * soft_gate(z_scores.get(a, 0.0), THETA[a])
               * soft_gate(z_scores.get(b, 0.0), THETA[b])
        for a, b, k in CONV_PAIRS
    )
    conv = min(conv_raw, 2.0)
    alert = compute_alert(risk, anomaly, conv)
    return compute_urban_score(alert), alert


def _incident_z(raw_incident: float, zone_id: str, global_bl: dict, zone_bl: dict) -> float:
    """Compute incident z-score from raw value + calibrated baseline."""
    bl = zone_bl.get(zone_id, {}).get("incident", global_bl.get("incident", BASELINE_DEFAULTS["incident"]))
    z = (raw_incident - bl["mu"]) / (bl["sigma"] + EPSILON)
    return max(-Z_CAP, min(Z_CAP, z))


def phase_1(db_path: Path, limit: int) -> Optional[List[dict]]:
    print("\n=== Phase 1 — Baseline Replay ===")
    print("  Strategy: use STORED z-scores (traffic/weather/event/transport)")
    print("            + compute incident z from raw_incident + calibration")

    rows, source_label = load_history(db_path, limit)
    if not rows:
        print("  ❌  signals_history is empty — cannot replay")
        return None

    print(f"  Source: {source_label}")
    print(f"  Rows loaded: {len(rows)}")

    # Load calibration (for incident z-score only) & vacances (for phi)
    global_bl, zone_bl, _, _ = _load_calibration(db_path)
    vacances = _load_vacances(db_path)
    years = set()
    for r in rows:
        try:
            years.add(datetime.fromisoformat(r["ts"]).year)
        except Exception:
            pass
    holidays = set()
    for y in years:
        holidays |= _jours_feries(y)

    # Group rows by timestamp for spread computation
    by_ts: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by_ts[r["ts"]].append(r)

    diffs = []
    scored_rows = []

    for ts, zone_rows in by_ts.items():
        phi = reconstruct_phi(ts, vacances, holidays)

        # Pass 1: compute alert for each zone (for spread)
        alert_map = {}
        zone_data = {}
        for r in zone_rows:
            zid = r["zone_id"]
            z_scores = {
                "traffic":   r["traffic"]   or 0.0,
                "weather":   r["weather"]   or 0.0,
                "event":     r["event"]     or 0.0,
                "transport": r["transport"] or 0.0,
                "incident":  _incident_z(r["raw_incident"] or 0.0, zid, global_bl, zone_bl),
            }
            _, alert = _score_from_z(z_scores, phi)
            alert_map[zid] = alert
            zone_data[zid] = (z_scores, alert, r)

        # Pass 2: compute score with spread
        for zid, (z_scores, alert, r) in zone_data.items():
            spread = compute_spread(zid, alert_map)
            calc_score = compute_urban_score(alert, spread)
            stored_score = r["urban_score"]
            if stored_score is not None:
                diff = abs(calc_score - stored_score)
                diffs.append(diff)
                scored_rows.append({
                    "ts": ts, "zone_id": zid,
                    "stored": stored_score, "calc": calc_score, "diff": diff,
                    "z_scores": z_scores, "phi": phi,
                })

    if not diffs:
        print("  ❌  No comparable rows found")
        return None

    mean_diff = sum(diffs) / len(diffs)
    max_diff = max(diffs)
    within_1 = sum(1 for d in diffs if d <= 1) / len(diffs) * 100
    within_5 = sum(1 for d in diffs if d <= 5) / len(diffs) * 100

    print(f"  Rows compared    : {len(diffs)}")
    print(f"  Mean deviation   : {mean_diff:.3f} pts")
    print(f"  Max deviation    : {max_diff:.3f} pts")
    print(f"  Within ±1pt      : {within_1:.1f}%")
    print(f"  Within ±5pt      : {within_5:.1f}%")

    # Show worst 5
    worst = sorted(scored_rows, key=lambda x: x["diff"], reverse=True)[:5]
    if worst and worst[0]["diff"] > 1:
        print(f"\n  Top deviations:")
        for w in worst:
            print(f"    {w['zone_id']:<14} {w['ts'][:19]}  stored={w['stored']:>2}  calc={w['calc']:>2}  Δ={w['diff']:>2}")

    if mean_diff <= 1:
        print(f"\n  ✅  Baseline faithful (mean deviation {mean_diff:.3f} ≤ 1pt)")
    elif mean_diff <= 3:
        print(f"\n  ⚠️  Moderate deviation (mean {mean_diff:.3f} ≤ 3pt) — likely phi or spread delta")
    else:
        print(f"\n  ❌  Parameter mismatch (mean {mean_diff:.3f} > 3pt) — stopping before Phase 2")
        return None

    return scored_rows


# ═════════════════════════════════════════════════════════════════════════════
# Phase 2 — Sensitivity Analysis
# ═════════════════════════════════════════════════════════════════════════════

def _perturbed_score(
    z_scores: dict, phi: float, zone_id: str, alert_map_base: dict,
    phi_factor: float = 1.0,
    theta_delta: float = 0.0,
    w_traffic_delta: float = 0.0,
    w_incident_delta: float = 0.0,
    lambda1_factor: float = 1.0,
) -> int:
    """Compute score from z-scores with one perturbation applied."""
    adj_phi = phi * phi_factor

    # Perturbed weights (renormalize to Σ=1)
    w = dict(WEIGHTS)
    if w_traffic_delta != 0:
        w["traffic"] += w_traffic_delta
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
    if w_incident_delta != 0:
        w = dict(WEIGHTS)
        w["incident"] += w_incident_delta
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}

    # Perturbed thetas
    adj_theta = {s: max(v + theta_delta, 0.1) for s, v in THETA.items()}

    # Risk from z-scores (all in NEUTRAL_WHEN_LOW → max(z, 0))
    risk = adj_phi * sum(w[s] * max(z_scores.get(s, 0.0), 0.0) for s in SIGNALS)

    # Anomaly
    anomaly = sum(ALPHA[s] * max(z_scores.get(s, 0.0), 0.0) for s in SIGNALS)

    # Conv with perturbed thetas
    conv_raw = sum(
        BETA[k] * soft_gate(z_scores.get(a, 0.0), adj_theta[a])
               * soft_gate(z_scores.get(b, 0.0), adj_theta[b])
        for a, b, k in CONV_PAIRS
    )
    conv = min(conv_raw, 2.0)

    adj_l1 = LAMBDA["l1"] * lambda1_factor
    alert = adj_l1 * risk + LAMBDA["l2"] * anomaly + LAMBDA["l3"] * conv
    spread = compute_spread(zone_id, alert_map_base)
    return compute_urban_score(alert, spread)


def phase_2(scored_rows: List[dict]) -> List[dict]:
    print("\n=== Phase 2 — Sensitivity Analysis ===")

    perturbations = [
        ("phi_+15pct",       {"phi_factor": 1.15}),
        ("phi_-15pct",       {"phi_factor": 0.85}),
        ("theta_+0.5",       {"theta_delta": 0.5}),
        ("theta_-0.5",       {"theta_delta": -0.5}),
        ("w_traffic_+20pct", {"w_traffic_delta": WEIGHTS["traffic"] * 0.2}),
        ("w_traffic_-20pct", {"w_traffic_delta": -WEIGHTS["traffic"] * 0.2}),
        ("w_incident_+20pct",{"w_incident_delta": WEIGHTS["incident"] * 0.2}),
        ("w_incident_-20pct",{"w_incident_delta": -WEIGHTS["incident"] * 0.2}),
        ("lambda1_+30pct",   {"lambda1_factor": 1.3}),
        ("lambda1_-30pct",   {"lambda1_factor": 0.7}),
    ]

    # Pre-compute alert_map per timestamp for spread (approximate alert from score)
    by_ts: Dict[str, Dict[str, float]] = defaultdict(dict)
    for r in scored_rows:
        by_ts[r["ts"]][r["zone_id"]] = r.get("calc", 0)

    results = []
    for name, params in perturbations:
        deltas = []
        for r in scored_rows:
            baseline_score = r["calc"]
            alert_map = {}
            for zid, score in by_ts[r["ts"]].items():
                alert_map[zid] = score * 0.02  # approximate alert from score

            perturbed = _perturbed_score(
                r["z_scores"], r["phi"], r["zone_id"], alert_map, **params,
            )
            deltas.append(abs(perturbed - baseline_score))

        mean_d = sum(deltas) / len(deltas) if deltas else 0
        max_d = max(deltas) if deltas else 0
        std_d = (sum((d - mean_d) ** 2 for d in deltas) / len(deltas)) ** 0.5 if deltas else 0

        results.append({"name": name, "mean": mean_d, "max": max_d, "std": std_d})

    results.sort(key=lambda x: x["mean"], reverse=True)

    print(f"  {'Hypothesis':<24} {'Mean Δ':>8} {'Max Δ':>8} {'Std Δ':>8}")
    print(f"  {'-'*24} {'-'*8} {'-'*8} {'-'*8}")
    for r in results:
        flag = " ⚠️" if r["mean"] > 5 else ""
        print(f"  {r['name']:<24} {r['mean']:>8.3f} {r['max']:>8.3f} {r['std']:>8.3f}{flag}")

    return results


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3 — Model Risk Contribution
# ═════════════════════════════════════════════════════════════════════════════

def phase_3(sensitivity_results: List[dict]):
    print("\n=== Phase 3 — Model Risk Contribution ===")

    # Group perturbations by hypothesis family (max of +/- for each)
    families = {
        "phi":       ["phi_+15pct", "phi_-15pct"],
        "theta":     ["theta_+0.5", "theta_-0.5"],
        "w_traffic": ["w_traffic_+20pct", "w_traffic_-20pct"],
        "w_incident":["w_incident_+20pct", "w_incident_-20pct"],
        "lambda1":   ["lambda1_+30pct", "lambda1_-30pct"],
    }

    lookup = {r["name"]: r for r in sensitivity_results}
    contributions = []

    for family, members in families.items():
        sensitivity = max(lookup[m]["mean"] for m in members if m in lookup)
        contributions.append({"family": family, "sensitivity": sensitivity})

    total_sensitivity = sum(c["sensitivity"] for c in contributions)
    if total_sensitivity == 0:
        print("  All sensitivities are 0 — model is completely insensitive (check data)")
        return

    for c in contributions:
        c["pct"] = c["sensitivity"] / total_sensitivity * 100

    contributions.sort(key=lambda x: x["pct"], reverse=True)

    max_bar = 40
    max_pct = max(c["pct"] for c in contributions)

    print(f"  {'Hypothesis':<20} {'Mean Δ':>8} {'Contribution':>14}")
    print(f"  {'-'*20} {'-'*8} {'-'*14}")
    for c in contributions:
        bar_len = int(c["pct"] / max_pct * max_bar) if max_pct > 0 else 0
        bar = "█" * bar_len
        print(f"  {c['family']:<20} {c['sensitivity']:>8.3f}    {c['pct']:>5.1f}%  {bar}")

    dominant = contributions[0]
    if dominant["pct"] > 50:
        print(f"\n  ⚠️  Dominant hypothesis: '{dominant['family']}' contributes "
              f"{dominant['pct']:.1f}% of model risk")

    for c in contributions:
        if c["sensitivity"] > 5:
            print(f"  ⚠️  '{c['family']}' mean Δ = {c['sensitivity']:.3f} > 5pt — "
                  f"recalibration recommended")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Urban Score Engine — Model Risk Validation",
    )
    parser.add_argument("--db", default="data/urban_signals.db",
                        help="Path to SQLite database (default: data/urban_signals.db)")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max rows to load from signals_history (default: 5000)")
    parser.add_argument("--phase", type=int, default=0, choices=[0, 1, 2, 3],
                        help="Run a single phase (0 = all phases)")
    args = parser.parse_args()

    db_path = Path(args.db)
    run_all = args.phase == 0

    print("=" * 60)
    print("  Urban Score Engine — Model Risk Validation")
    print("=" * 60)
    print(f"  Config: WEIGHTS={WEIGHTS}")
    print(f"  Config: LAMBDA={LAMBDA}")

    # Phase 0 — always runs (no DB needed)
    if run_all or args.phase == 0:
        phase_0_ok = phase_0()

    # Phases 1-3 need the DB
    if (run_all or args.phase >= 1) and args.phase != 0:
        if not db_path.exists():
            print(f"\n  ❌  Database not found: {db_path}")
            sys.exit(1)

    if run_all and not db_path.exists():
        print(f"\n  ⚠️  Database not found: {db_path} — skipping Phases 1-3")
        print("\n" + "=" * 60)
        print("  Validation complete (Phase 0 only).")
        print("=" * 60)
        sys.exit(0)

    scored_rows = None
    if run_all or args.phase == 1:
        scored_rows = phase_1(db_path, args.limit)

    if run_all or args.phase == 2:
        if scored_rows is None and args.phase == 2:
            scored_rows = phase_1(db_path, args.limit)
        if scored_rows is None:
            print("\n  ❌  Phase 1 failed — cannot proceed to Phase 2")
        else:
            sensitivity = phase_2(scored_rows)

            if run_all or args.phase == 3:
                phase_3(sensitivity)

    if args.phase == 3:
        scored_rows = phase_1(db_path, args.limit)
        if scored_rows:
            sensitivity = phase_2(scored_rows)
            phase_3(sensitivity)

    print("\n" + "=" * 60)
    print("  Validation complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
