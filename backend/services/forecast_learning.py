"""
Forecast auto-learning — ADR-018
Adjusts forecast scenario weights and decay half-lives based on
historical prediction accuracy (bias from forecast_history).

Runs weekly alongside calibration. Only touches forecast-internal
parameters — never modifies live scoring formula.
"""

import logging
from typing import Dict, Any, Optional

from config import (
    FORECAST_LEARN_DEFAULTS,
    FORECAST_LEARN_BOUNDS,
    FORECAST_LEARN_MIN_N,
    FORECAST_LEARN_ALPHA,
    FORECAST_LEARN_MAX_STEP,
)

log = logging.getLogger("forecast_learning")

# ── Module state ──────────────────────────────────────────────────────────────
_params: Dict[str, Any] = {
    "scenario_weights": dict(FORECAST_LEARN_DEFAULTS["scenario_weights"]),
    "scenario_weights_no_proj": dict(FORECAST_LEARN_DEFAULTS["scenario_weights_no_proj"]),
    "decay_halflife_min": FORECAST_LEARN_DEFAULTS["decay_halflife_min"],
    "incident_halflife_min": FORECAST_LEARN_DEFAULTS["incident_halflife_min"],
}


def get_forecast_params() -> Dict[str, Any]:
    """Return current learned forecast parameters (copy)."""
    return {
        "scenario_weights": dict(_params["scenario_weights"]),
        "scenario_weights_no_proj": dict(_params["scenario_weights_no_proj"]),
        "decay_halflife_min": _params["decay_halflife_min"],
        "incident_halflife_min": _params["incident_halflife_min"],
    }


def set_forecast_params(params: Dict[str, Any]) -> None:
    """Apply learned params (from snapshot or learning cycle)."""
    if not params:
        return
    sw = params.get("scenario_weights")
    if sw and isinstance(sw, dict):
        validated = _validate_weights(sw)
        _params["scenario_weights"] = validated
    sw_np = params.get("scenario_weights_no_proj")
    if sw_np and isinstance(sw_np, dict):
        validated = _validate_weights(sw_np)
        _params["scenario_weights_no_proj"] = validated
    for key in ("decay_halflife_min", "incident_halflife_min"):
        if key in params and params[key] is not None:
            val = float(params[key])
            lo = FORECAST_LEARN_BOUNDS["halflife_min"]
            hi = FORECAST_LEARN_BOUNDS["halflife_max"]
            _params[key] = max(lo, min(hi, val))
    log.info("[forecast-learning] params applied: %s", _params)


def _validate_weights(weights: dict) -> dict:
    """Clamp each weight to bounds and normalize to sum=1."""
    lo = FORECAST_LEARN_BOUNDS["weight_min"]
    hi = FORECAST_LEARN_BOUNDS["weight_max"]
    clamped = {k: max(lo, min(hi, float(v))) for k, v in weights.items()}
    total = sum(clamped.values())
    if total == 0:
        return dict(weights)  # safety: return unchanged
    return {k: round(v / total, 4) for k, v in clamped.items()}


def compute_forecast_adjustments(accuracy_data: dict) -> Optional[Dict[str, Any]]:
    """
    Compute proposed parameter adjustments from forecast accuracy data.

    accuracy_data: output of get_forecast_accuracy() from forecast_storage.py
        Expected keys: by_horizon (list of dicts with horizon, bias, mae_clean, n)

    Returns proposed params dict, or None if insufficient data.
    """
    by_horizon = accuracy_data.get("by_horizon", [])
    if not by_horizon:
        log.warning("[forecast-learning] No horizon data — skipping")
        return None

    # ── Collect bias for short and extended horizons ──
    short_biases = []   # 30min, 60min, 2h
    ext_biases = []     # 6h, 12h, 24h
    short_horizons = {"30min", "60min", "2h"}
    ext_horizons = {"6h", "12h", "24h"}

    for h in by_horizon:
        horizon = h.get("horizon", "")
        n = h.get("n", 0)
        bias = h.get("bias")
        if n < FORECAST_LEARN_MIN_N or bias is None:
            continue
        if horizon in short_horizons:
            short_biases.append((n, bias))
        elif horizon in ext_horizons:
            ext_biases.append((n, bias))

    if not short_biases:
        log.info("[forecast-learning] Insufficient short-horizon data (n < %d)", FORECAST_LEARN_MIN_N)
        return None

    # ── Weighted average bias (weighted by n) ──
    short_bias = sum(n * b for n, b in short_biases) / sum(n for n, _ in short_biases)
    ext_bias = (sum(n * b for n, b in ext_biases) / sum(n for n, _ in ext_biases)) if ext_biases else 0.0

    alpha = FORECAST_LEARN_ALPHA
    max_step = FORECAST_LEARN_MAX_STEP

    # ── Adjust short-horizon scenario weights ──
    # bias > 0 → actual > predicted → model under-predicts → increase maintained
    # bias < 0 → actual < predicted → model over-predicts → increase persist
    correction = alpha * short_bias / 10.0  # normalize: bias is on 0-100 scale
    correction = max(-max_step, min(max_step, correction))

    new_weights = dict(_params["scenario_weights"])
    new_weights["maintained"] = new_weights.get("maintained", 0.55) + correction
    new_weights["persist"] = new_weights.get("persist", 0.25) - correction * 0.5
    if "proj" in new_weights:
        new_weights["proj"] = new_weights.get("proj", 0.20) - correction * 0.5
    new_weights = _validate_weights(new_weights)

    new_weights_np = dict(_params["scenario_weights_no_proj"])
    new_weights_np["maintained"] = new_weights_np.get("maintained", 0.70) + correction
    new_weights_np["persist"] = new_weights_np.get("persist", 0.30) - correction
    new_weights_np = _validate_weights(new_weights_np)

    # ── Adjust decay halflife (from short-horizon bias) ──
    # Under-predicting → signals decay too fast → increase halflife
    halflife_adj = alpha * short_bias  # ~1-2 min adjustment per cycle
    halflife_adj = max(-20, min(20, halflife_adj))  # clamp ±20 min
    new_decay = _params["decay_halflife_min"] + halflife_adj

    # ── Adjust incident halflife (from extended-horizon bias) ──
    inc_halflife_adj = alpha * ext_bias if ext_biases else 0.0
    inc_halflife_adj = max(-20, min(20, inc_halflife_adj))
    new_inc_halflife = _params["incident_halflife_min"] + inc_halflife_adj

    proposed = {
        "scenario_weights": new_weights,
        "scenario_weights_no_proj": new_weights_np,
        "decay_halflife_min": round(new_decay, 1),
        "incident_halflife_min": round(new_inc_halflife, 1),
    }

    log.info(
        "[forecast-learning] bias short=%.2f ext=%.2f | correction=%.4f | "
        "halflife_adj=%.1f inc_adj=%.1f",
        short_bias, ext_bias, correction, halflife_adj, inc_halflife_adj,
    )

    return proposed


def preview_learning(accuracy_data: dict) -> dict:
    """
    Dry-run: compute what would change without applying.
    Returns current, proposed, and deltas.
    """
    current = get_forecast_params()
    proposed = compute_forecast_adjustments(accuracy_data)
    if proposed is None:
        return {
            "status": "insufficient_data",
            "current_params": current,
            "proposed_params": None,
            "accuracy": accuracy_data,
        }

    deltas = {}
    for key in ("decay_halflife_min", "incident_halflife_min"):
        deltas[key] = round(proposed[key] - current[key], 1)
    for wkey in ("scenario_weights", "scenario_weights_no_proj"):
        deltas[wkey] = {
            k: round(proposed[wkey][k] - current[wkey].get(k, 0), 4)
            for k in proposed[wkey]
        }

    return {
        "status": "ready",
        "current_params": current,
        "proposed_params": proposed,
        "deltas": deltas,
        "accuracy": accuracy_data,
    }
