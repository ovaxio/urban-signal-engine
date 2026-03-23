"""
Urban Signal Engine — Forecast Accuracy Storage
=================================================
Persistence et évaluation des prévisions : save, evaluate, flag surprises, accuracy stats.
"""

import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.storage import _get_conn, DB_PATH, get_raw_incident_at

logger = logging.getLogger(__name__)


# ─── Throttle ─────────────────────────────────────────────────────────────────

FORECAST_SAVE_INTERVAL = 300  # 5 min
_last_forecast_save: Optional[datetime] = None


def _horizon_to_minutes(horizon: str) -> Optional[int]:
    """Convertit '30min', '2h', '24h' en minutes."""
    if horizon.endswith("min"):
        try:
            return int(horizon[:-3])
        except ValueError:
            return None
    elif horizon.endswith("h"):
        try:
            return int(horizon[:-1]) * 60
        except ValueError:
            return None
    return None


# ─── Save ─────────────────────────────────────────────────────────────────────

def should_save_forecasts() -> bool:
    """Vérifie si le throttle autorise une nouvelle sauvegarde batch."""
    now = datetime.now(timezone.utc)
    if _last_forecast_save and (now - _last_forecast_save).total_seconds() < FORECAST_SAVE_INTERVAL:
        return False
    return True


def save_forecast_history(
    zone_id: str,
    forecast: List[Dict[str, Any]],
    current_score: int,
    db_path: Path = DB_PATH,
) -> int:
    """
    Persiste les prévisions d'une zone pour évaluation ultérieure.
    Le throttle est géré par l'appelant via should_save_forecasts().
    """
    global _last_forecast_save
    now = datetime.now(timezone.utc)

    ts_now = now.isoformat(timespec="seconds")
    rows = []
    for f in forecast:
        horizon = f.get("horizon", "")
        predicted = f.get("urban_score", 0)
        minutes = _horizon_to_minutes(horizon)
        if minutes is None:
            continue
        target_dt = now + timedelta(minutes=minutes)
        rows.append({
            "ts_forecast": ts_now,
            "zone_id": zone_id,
            "horizon": horizon,
            "predicted_score": predicted,
            "target_ts": target_dt.isoformat(timespec="seconds"),
        })

    if not rows:
        return 0

    sql = """
        INSERT INTO forecast_history (ts_forecast, zone_id, horizon, predicted_score, target_ts)
        VALUES (:ts_forecast, :zone_id, :horizon, :predicted_score, :target_ts)
    """
    with _get_conn(db_path) as conn:
        conn.executemany(sql, rows)

    _last_forecast_save = now
    logger.debug("forecast_history : %d prévision(s) sauvegardée(s) pour %s.", len(rows), zone_id)
    return len(rows)


# ─── Evaluate ─────────────────────────────────────────────────────────────────

def evaluate_forecasts(
    scores: List[Dict[str, Any]],
    tolerance_minutes: int = 5,
    db_path: Path = DB_PATH,
) -> int:
    """
    Compare les forecasts passés avec les scores actuels.
    Pour chaque forecast dont target_ts est dans [now - tolerance, now + tolerance]
    et qui n'a pas encore été évalué, on enregistre le score réel et le delta.
    Si |delta| > 15 et raw_incident > 0.5 à l'instant évalué → incident_surprise = 1 (ADR-014).
    """
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")
    window_end = (now + timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")

    score_map = {z["zone_id"]: z["urban_score"] for z in scores}

    sql_select = """
        SELECT id, zone_id, predicted_score
        FROM forecast_history
        WHERE target_ts >= ? AND target_ts <= ?
          AND actual_score IS NULL
    """
    sql_update = """
        UPDATE forecast_history
        SET actual_score = ?, delta = ?, evaluated_at = ?, incident_surprise = ?
        WHERE id = ?
    """

    evaluated = 0
    eval_ts = now.isoformat(timespec="seconds")

    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        pending = conn.execute(sql_select, (window_start, window_end)).fetchall()

        for row in pending:
            actual = score_map.get(row["zone_id"])
            if actual is None:
                continue
            delta = actual - row["predicted_score"]
            # Inline incident_surprise detection (ADR-014)
            surprise = 0
            if abs(delta) > 15:
                raw_inc = get_raw_incident_at(row["zone_id"], eval_ts, db_path=db_path)
                if raw_inc > 0.5:
                    surprise = 1
            conn.execute(sql_update, (actual, delta, eval_ts, surprise, row["id"]))
            evaluated += 1

    if evaluated:
        logger.info("forecast_history : %d prévision(s) évaluée(s).", evaluated)
    return evaluated


# ─── Flag Incident Surprises ──────────────────────────────────────────────────

def flag_incident_surprises(
    incident_events: Dict[str, List[Dict]] = None,
    db_path: Path = DB_PATH,
) -> int:
    """
    Backfill : marque les forecasts évalués comme 'incident_surprise'
    en vérifiant raw_incident dans signals_history au moment de l'évaluation.
    Critères : |delta| > 15 AND raw_incident > 0.5 à evaluated_at ±5min (ADR-014).
    Le paramètre incident_events est conservé pour compatibilité mais ignoré
    (la détection inline dans evaluate_forecasts() couvre les nouveaux cas).
    """
    sql_select = """
        SELECT id, zone_id, evaluated_at
        FROM forecast_history
        WHERE actual_score IS NOT NULL
          AND incident_surprise = 0
          AND ABS(delta) > 15
          AND evaluated_at IS NOT NULL
    """
    sql_update = "UPDATE forecast_history SET incident_surprise = 1 WHERE id = ?"

    flagged = 0
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql_select).fetchall()

    for row in rows:
        raw_inc = get_raw_incident_at(row["zone_id"], row["evaluated_at"], db_path=db_path)
        if raw_inc > 0.5:
            with _get_conn(db_path) as conn:
                conn.execute(sql_update, (row["id"],))
            flagged += 1

    if flagged:
        logger.info("forecast_history : %d prévision(s) marquée(s) incident_surprise (backfill).", flagged)
    return flagged


# ─── Accuracy Stats ───────────────────────────────────────────────────────────

def get_forecast_accuracy(
    zone_id: Optional[str] = None,
    horizon: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 200,
    db_path: Path = DB_PATH,
) -> Dict[str, Any]:
    """
    Stats de précision des forecasts évalués :
    MAE global et par horizon, taux d'incident_surprise, dernières évaluations.
    since: ISO date string (YYYY-MM-DD or full ISO) — filtre evaluated_at >= since.
    """
    where_clauses = ["actual_score IS NOT NULL"]
    params: list = []
    if zone_id:
        where_clauses.append("zone_id = ?")
        params.append(zone_id)
    if horizon:
        where_clauses.append("horizon = ?")
        params.append(horizon)
    if since:
        where_clauses.append("evaluated_at >= ?")
        params.append(since)

    where = " AND ".join(where_clauses)

    sql_stats = f"""
        SELECT
            horizon,
            COUNT(*)                                            AS n,
            ROUND(AVG(ABS(delta)), 1)                           AS mae,
            ROUND(AVG(CASE WHEN incident_surprise = 0 THEN ABS(delta) END), 1) AS mae_clean,
            SUM(CASE WHEN incident_surprise = 1 THEN 1 ELSE 0 END) AS n_surprise,
            ROUND(AVG(delta), 1)                                AS bias,
            MIN(delta)                                          AS min_delta,
            MAX(delta)                                          AS max_delta
        FROM forecast_history
        WHERE {where}
        GROUP BY horizon
        ORDER BY horizon
    """

    sql_recent = f"""
        SELECT ts_forecast, zone_id, horizon, predicted_score,
               actual_score, delta, incident_surprise, evaluated_at
        FROM forecast_history
        WHERE {where}
        ORDER BY evaluated_at DESC
        LIMIT ?
    """

    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        stats = [dict(r) for r in conn.execute(sql_stats, params).fetchall()]
        recent = [dict(r) for r in conn.execute(sql_recent, params + [limit]).fetchall()]

    total_n = sum(s["n"] for s in stats)
    total_mae = round(sum(s["mae"] * s["n"] for s in stats) / total_n, 1) if total_n else None
    total_surprise = sum(s["n_surprise"] for s in stats)

    return {
        "total_evaluated": total_n,
        "mae_global": total_mae,
        "incident_surprises": total_surprise,
        "by_horizon": stats,
        "recent": recent[:50],
    }
