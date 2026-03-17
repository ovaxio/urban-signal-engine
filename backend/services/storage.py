"""
Urban Signal Engine — Storage Service
Persistence SQLite pour signaux et scores historiques.
"""

import csv
import gzip
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "urban_signal.db"
SEED_PATH = Path(__file__).parent.parent / "data" / "seed_signals_history.csv.gz"

CREATE_SIGNALS_HISTORY = """
CREATE TABLE IF NOT EXISTS signals_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT    NOT NULL,
    zone_id           TEXT    NOT NULL,
    traffic           REAL,
    weather           REAL,
    event             REAL,
    transport         REAL,
    urban_score       REAL    NOT NULL,
    level             TEXT    NOT NULL,
    raw_traffic       REAL,
    raw_weather       REAL,
    raw_event         REAL,
    raw_transport     REAL,
    raw_incident      REAL
);
"""

CREATE_ALERTS_LOG = """
CREATE TABLE IF NOT EXISTS alerts_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    zone_id     TEXT    NOT NULL,
    zone_name   TEXT,
    alert_type  TEXT    NOT NULL,
    urban_score INTEGER,
    prev_score  INTEGER,
    level       TEXT
);
"""

CREATE_VACANCES = """
CREATE TABLE IF NOT EXISTS calendar_vacances (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    description TEXT,
    zone        TEXT DEFAULT 'A',
    fetched_at  TEXT NOT NULL
);
"""

CREATE_FORECAST_HISTORY = """
CREATE TABLE IF NOT EXISTS forecast_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_forecast     TEXT    NOT NULL,
    zone_id         TEXT    NOT NULL,
    horizon         TEXT    NOT NULL,
    predicted_score INTEGER NOT NULL,
    target_ts       TEXT    NOT NULL,
    actual_score    INTEGER,
    delta           INTEGER,
    incident_surprise INTEGER DEFAULT 0,
    evaluated_at    TEXT
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sh_zone_ts  ON signals_history (zone_id, ts);",
    "CREATE INDEX IF NOT EXISTS idx_sh_ts       ON signals_history (ts);",
    "CREATE INDEX IF NOT EXISTS idx_al_ts       ON alerts_log (ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_fh_target   ON forecast_history (target_ts, zone_id);",
    "CREATE INDEX IF NOT EXISTS idx_fh_zone     ON forecast_history (zone_id, ts_forecast);",
]

# Migration : ajoute les colonnes raw si elles n'existent pas encore (base existante)
MIGRATE_ADD_RAW_COLUMNS = [
    "ALTER TABLE signals_history ADD COLUMN raw_traffic   REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_weather   REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_event     REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_transport REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_incident  REAL;",
]


# ─── Initialisation ────────────────────────────────────────────────────────────

def init_db(db_path: Path = DB_PATH) -> None:
    """
    Crée le répertoire data/ et initialise la base SQLite.
    Idempotent — safe à appeler au démarrage de l'app.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _get_conn(db_path) as conn:
        conn.execute(CREATE_SIGNALS_HISTORY)
        conn.execute(CREATE_ALERTS_LOG)
        conn.execute(CREATE_VACANCES)
        conn.execute(CREATE_FORECAST_HISTORY)
        for idx_sql in CREATE_INDEXES:
            conn.execute(idx_sql)
        _migrate_raw_columns(conn)
        _seed_signals_history(conn, db_path)

    logger.info("DB initialisée : %s", db_path)


def _seed_signals_history(conn: sqlite3.Connection, db_path: Path = DB_PATH) -> None:
    """
    Charge le fichier seed CSV gzippé dans signals_history si la table est vide.
    Utilisé sur Render (filesystem éphémère) pour restaurer les profils horaires.

    Les timestamps sont décalés pour que le relevé le plus récent du seed
    corresponde à l'heure courante — les historiques et rapports d'impact
    restent ainsi cohérents temporellement.
    """
    row_count = conn.execute("SELECT COUNT(*) FROM signals_history").fetchone()[0]
    if row_count > 0:
        logger.info("signals_history contient déjà %d lignes, seed ignoré.", row_count)
        return

    seed = SEED_PATH if db_path == DB_PATH else db_path.parent / "seed_signals_history.csv.gz"
    if not seed.exists():
        logger.warning("Fichier seed introuvable : %s — profils horaires vides.", seed)
        return

    logger.info("Seed signals_history depuis %s …", seed)

    # ── Passe 1 : trouver le timestamp max pour calculer le décalage ──
    max_ts: Optional[datetime] = None
    with gzip.open(seed, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row.get("ts", "")
            if ts_str:
                ts = datetime.fromisoformat(ts_str)
                if max_ts is None or ts > max_ts:
                    max_ts = ts

    if max_ts is None:
        logger.warning("Seed vide ou sans timestamps, abandon.")
        return

    now = datetime.now(timezone.utc)
    delta = now - max_ts
    logger.info("Seed ts shift : max_ts=%s, now=%s, delta=%s", max_ts.isoformat(), now.isoformat(), delta)

    # ── Passe 2 : insertion avec timestamps décalés ──
    cols = (
        "ts", "zone_id", "traffic", "weather", "event", "transport",
        "urban_score", "level", "raw_traffic", "raw_weather",
        "raw_event", "raw_transport", "raw_incident",
    )
    numeric = {
        "traffic", "weather", "event", "transport", "urban_score",
        "raw_traffic", "raw_weather", "raw_event", "raw_transport", "raw_incident",
    }
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO signals_history ({', '.join(cols)}) VALUES ({placeholders})"

    inserted = 0
    with gzip.open(seed, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch: list = []
        for row in reader:
            values = []
            for c in cols:
                v = row.get(c, "")
                if v == "":
                    values.append(None)
                elif c == "ts":
                    shifted = datetime.fromisoformat(v) + delta
                    values.append(shifted.isoformat())
                elif c in numeric:
                    values.append(float(v))
                else:
                    values.append(v)
            batch.append(tuple(values))
            if len(batch) >= 2000:  # SQLite max params = 32767 / 13 cols ≈ 2520
                conn.executemany(sql, batch)
                inserted += len(batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
            inserted += len(batch)
    conn.commit()
    logger.info("Seed terminé : %d lignes insérées (décalage %s).", inserted, delta)


def _migrate_raw_columns(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes raw_ si absentes (migration non destructive)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(signals_history)")}
    for sql in MIGRATE_ADD_RAW_COLUMNS:
        col = sql.split("ADD COLUMN")[1].strip().split()[0]
        if col not in existing:
            try:
                conn.execute(sql)
                logger.info("Migration : colonne '%s' ajoutée.", col)
            except sqlite3.OperationalError as e:
                logger.warning("Migration skip '%s' : %s", col, e)


# ─── Calendrier scolaire ──────────────────────────────────────────────────────

def get_vacances(db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Retourne les vacances scolaires depuis la DB."""
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT start_date, end_date, description FROM calendar_vacances WHERE zone = 'A' ORDER BY start_date"
        ).fetchall()
    from datetime import date as _date
    return [
        {"start": _date.fromisoformat(r[0]), "end": _date.fromisoformat(r[1]), "description": r[2]}
        for r in rows
    ]


def save_vacances(periods: List[Dict[str, Any]], db_path: Path = DB_PATH) -> int:
    """Remplace les vacances en DB par les nouvelles périodes."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn(db_path) as conn:
        conn.execute("DELETE FROM calendar_vacances WHERE zone = 'A'")
        for p in periods:
            conn.execute(
                "INSERT INTO calendar_vacances (start_date, end_date, description, zone, fetched_at) VALUES (?, ?, ?, 'A', ?)",
                (str(p["start"]), str(p["end"]), p.get("description", ""), now),
            )
    logger.info("Vacances scolaires sauvegardées : %d périodes", len(periods))
    return len(periods)


# ─── Persistence ───────────────────────────────────────────────────────────────

def save_scores_history(
    scores: list[dict[str, Any]],
    db_path: Path = DB_PATH,
) -> int:
    """
    Persiste un batch de scores en base.

    Paramètre attendu (liste de dicts) :
        {
            "zone_id":     str,
            "signals":     dict,   # valeurs normalisées
            "raw_signals": dict,   # valeurs brutes ← NOUVEAU (optionnel)
            "urban_score": float,
            "level":       str,
            "ts":          str | None
        }

    Retourne le nombre de lignes insérées.
    """
    if not scores:
        logger.debug("save_scores_history : liste vide, rien à persister.")
        return 0

    ts_now = _utc_now()
    rows = [_build_row(entry, ts_now) for entry in scores]

    sql = """
        INSERT INTO signals_history
            (ts, zone_id,
             traffic, weather, event, transport,
             raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
             urban_score, level)
        VALUES
            (:ts, :zone_id,
             :traffic, :weather, :event, :transport,
             :raw_traffic, :raw_weather, :raw_event, :raw_transport, :raw_incident,
             :urban_score, :level)
    """

    with _get_conn(db_path) as conn:
        conn.executemany(sql, rows)

    logger.info("save_scores_history : %d ligne(s) insérée(s).", len(rows))
    return len(rows)


# ─── Lecture ───────────────────────────────────────────────────────────────────

def get_zone_history(
    zone_id: str,
    limit: int = 200,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    sql = """
        SELECT ts, zone_id, traffic, weather, event, transport,
               raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
               urban_score, level
        FROM   signals_history
        WHERE  zone_id = ?
        ORDER  BY ts DESC
        LIMIT  ?
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (zone_id, limit)).fetchall()
    return [dict(r) for r in rows]


def get_signal_stats(
    zone_id: str,
    signal: str,
    use_raw: bool = True,
    db_path: Path = DB_PATH,
) -> Optional[Dict[str, Union[float, int]]]:
    """
    Calcule mu / sigma / min / max / count pour un signal.
    use_raw=True  → colonnes raw_ (valeurs brutes, pour recalibration)
    use_raw=False → colonnes normalisées (debug)
    """
    allowed = {"traffic", "weather", "event", "transport", "incident"}
    if signal not in allowed:
        raise ValueError(f"Signal invalide : {signal!r}. Attendu : {allowed}")

    col = f"raw_{signal}" if use_raw else signal

    sql = f"""
        SELECT
            COUNT({col})                                          AS count,
            AVG({col})                                            AS mu,
            AVG({col} * {col}) - AVG({col}) * AVG({col})         AS variance,
            MIN({col})                                            AS min,
            MAX({col})                                            AS max
        FROM signals_history
        WHERE zone_id = ?
          AND {col} IS NOT NULL
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, (zone_id,)).fetchone()

    if not row or row["count"] == 0:
        return None

    variance = max(row["variance"] or 0.0, 0.0)
    return {
        "count": row["count"],
        "mu":    round(row["mu"], 4),
        "sigma": round(variance ** 0.5, 4),
        "min":   round(row["min"], 4),
        "max":   round(row["max"], 4),
    }


def get_calibration_baselines(
    min_count: int = 96,
    db_path: Path = DB_PATH,
) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Calcule les baselines globales (toutes zones) depuis les raw_signals.
    Retourne None si pas assez de données (< min_count relevés).
    Utilisé par scoring.py pour recalibrer BASELINE automatiquement.
    """
    sql = """
        SELECT COUNT(*) as n FROM signals_history WHERE raw_traffic IS NOT NULL
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        n = conn.execute(sql).fetchone()["n"]

    if n < min_count:
        logger.info("Recalibration différée : %d/%d relevés raw disponibles.", n, min_count)
        return None

    # Sigma minimum physiquement raisonnable par signal.
    # Évite qu'un historique quasi-constant (ex: event=0.0 toujours) produise
    # sigma≈0 et des normalisations explosives.
    MIN_SIGMA = {
        "traffic":   0.15,
        "weather":   0.10,
        "event":     0.20,   # signal naturellement non-stationnaire
        "transport": 0.10,
        "incident":  0.15,
    }

    baselines = {}
    # event exclu : non-stationnaire (calendrier statique, peut être tout-à-zéro)
    for signal in ("traffic", "weather", "transport", "incident"):
        col = f"raw_{signal}"
        sql = f"""
            SELECT
                AVG({col})                                        AS mu,
                AVG({col} * {col}) - AVG({col}) * AVG({col})     AS variance
            FROM signals_history
            WHERE {col} IS NOT NULL
        """
        with _get_conn(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql).fetchone()

        if row and row["mu"] is not None:
            variance = max(row["variance"] or 0.0, 0.0)
            sigma    = max(variance ** 0.5, MIN_SIGMA[signal])
            baselines[signal] = {
                "mu":    round(row["mu"], 4),
                "sigma": round(sigma, 4),
            }

    logger.info("Baselines recalibrées depuis %d relevés : %s", n, baselines)
    return baselines if baselines else None


def get_calibration_baselines_per_zone(
    min_count: int = 48,
    db_path: Path = DB_PATH,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Calcule les baselines par zone depuis les raw_signals.
    Retourne un dict zone_id → signal → {mu, sigma}.
    Les zones avec moins de min_count relevés sont ignorées (baseline globale utilisée).
    Le signal event est exclu (historique non-stationnaire).
    """
    MIN_SIGMA = {
        "traffic":   0.15,
        "weather":   0.10,
        "transport": 0.10,
        "incident":  0.15,
    }

    sql = """
        SELECT
            zone_id,
            COUNT(raw_traffic)                                                AS n,
            AVG(raw_traffic)                                                  AS mu_traffic,
            AVG(raw_traffic*raw_traffic) - AVG(raw_traffic)*AVG(raw_traffic)  AS var_traffic,
            AVG(raw_weather)                                                  AS mu_weather,
            AVG(raw_weather*raw_weather) - AVG(raw_weather)*AVG(raw_weather)  AS var_weather,
            AVG(raw_transport)                                                AS mu_transport,
            AVG(raw_transport*raw_transport) - AVG(raw_transport)*AVG(raw_transport) AS var_transport,
            AVG(raw_incident)                                                 AS mu_incident,
            AVG(raw_incident*raw_incident) - AVG(raw_incident)*AVG(raw_incident)     AS var_incident
        FROM signals_history
        WHERE raw_traffic IS NOT NULL
        GROUP BY zone_id
    """

    result: Dict[str, Dict[str, Dict[str, float]]] = {}
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()

    for row in rows:
        if row["n"] < min_count:
            continue
        zone_id = row["zone_id"]
        zone_bl: Dict[str, Dict[str, float]] = {}
        for signal in ("traffic", "weather", "transport", "incident"):
            mu  = row[f"mu_{signal}"]
            var = row[f"var_{signal}"] or 0.0
            if mu is None:
                continue
            sigma = max(max(var, 0.0) ** 0.5, MIN_SIGMA[signal])
            zone_bl[signal] = {"mu": round(mu, 4), "sigma": round(sigma, 4)}
        if zone_bl:
            result[zone_id] = zone_bl

    logger.info(
        "Baselines par zone calculées pour %d zones (%d relevés min).",
        len(result), min_count,
    )
    return result


# ─── Impact Report ────────────────────────────────────────────────────────────

def get_history_range(
    start: str,
    end: str,
    zone_id: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    """
    Retourne l'historique entre start et end (ISO).
    Si zone_id est fourni, filtre sur cette zone.
    """
    if zone_id:
        sql = """
            SELECT ts, zone_id, traffic, weather, event, transport,
                   raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
                   urban_score, level
            FROM   signals_history
            WHERE  ts >= ? AND ts <= ? AND zone_id = ?
            ORDER  BY ts ASC
        """
        params: tuple = (start, end, zone_id)
    else:
        sql = """
            SELECT ts, zone_id, traffic, weather, event, transport,
                   raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
                   urban_score, level
            FROM   signals_history
            WHERE  ts >= ? AND ts <= ?
            ORDER  BY ts ASC
        """
        params = (start, end)

    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_hourly_signal_profiles(
    zone_id: str,
    day_type: str = None,
    min_count: int = 3,
    db_path: Path = DB_PATH,
) -> Dict[int, Dict[str, float]]:
    """
    Calcule la moyenne des signaux bruts par heure pour une zone.
    Retourne un dict heure (0-23) → {traffic, weather, event, transport, incident}.
    Si day_type est fourni (semaine/mercredi/vacances/weekend), filtre par jour.
    Les heures avec moins de min_count relevés sont exclues.
    """
    # On extrait l'heure depuis le timestamp ISO
    # day_of_week: 0=dimanche en SQLite strftime('%w'), on convertit en Python (0=lundi)
    signals = ("traffic", "weather", "event", "transport", "incident")
    cols_avg = ", ".join(f"AVG(raw_{s}) AS avg_{s}" for s in signals)
    cols_count = "COUNT(raw_traffic) AS n"

    where_clauses = ["zone_id = ?", "raw_traffic IS NOT NULL"]
    params: list = [zone_id]

    # Filtrage par day_type via le jour de semaine SQLite
    if day_type == "weekend":
        # SQLite %w: 0=dimanche, 6=samedi
        where_clauses.append("CAST(strftime('%w', ts) AS INTEGER) IN (0, 6)")
    elif day_type == "mercredi":
        where_clauses.append("CAST(strftime('%w', ts) AS INTEGER) = 3")
    elif day_type in ("semaine", "vacances"):
        # Jours de semaine (lun-ven sauf mercredi) — vacances vs semaine
        # ne peut pas être distingué par SQL seul, on filtre semaine complète
        where_clauses.append("CAST(strftime('%w', ts) AS INTEGER) IN (1, 2, 4, 5)")

    where = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            CAST(strftime('%H', ts) AS INTEGER) AS hour,
            {cols_count},
            {cols_avg}
        FROM signals_history
        WHERE {where}
        GROUP BY hour
        ORDER BY hour
    """

    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()

    result: Dict[int, Dict[str, float]] = {}
    for row in rows:
        if row["n"] < min_count:
            continue
        h = row["hour"]
        profile: Dict[str, float] = {}
        for s in signals:
            val = row[f"avg_{s}"]
            if val is not None:
                profile[s] = round(val, 4)
        if profile:
            result[h] = profile

    logger.debug(
        "Profils horaires %s (day_type=%s) : %d heures couvertes",
        zone_id, day_type, len(result),
    )
    return result


def get_alerts_range(
    start: str,
    end: str,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    """Retourne les alertes entre start et end (ISO)."""
    sql = """
        SELECT ts, zone_id, zone_name, alert_type, urban_score, prev_score, level
        FROM   alerts_log
        WHERE  ts >= ? AND ts <= ?
        ORDER  BY ts ASC
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (start, end)).fetchall()
    return [dict(r) for r in rows]


# ─── Alertes ───────────────────────────────────────────────────────────────────

def save_alerts(alerts: list[dict[str, Any]], db_path: Path = DB_PATH) -> int:
    """Persiste une liste d'alertes en base."""
    if not alerts:
        return 0
    sql = """
        INSERT INTO alerts_log (ts, zone_id, zone_name, alert_type, urban_score, prev_score, level)
        VALUES (:ts, :zone_id, :zone_name, :alert_type, :urban_score, :prev_score, :level)
    """
    with _get_conn(db_path) as conn:
        conn.executemany(sql, alerts)
    logger.info("save_alerts : %d alerte(s) persistée(s).", len(alerts))
    return len(alerts)


def get_recent_alerts(limit: int = 50, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Retourne les dernières alertes, ordre antéchronologique."""
    sql = """
        SELECT ts, zone_id, zone_name, alert_type, urban_score, prev_score, level
        FROM   alerts_log
        ORDER  BY ts DESC
        LIMIT  ?
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ─── Forecast Accuracy Tracking ───────────────────────────────────────────────

# Throttle : on ne sauvegarde les forecasts qu'une fois toutes les FORECAST_SAVE_INTERVAL secondes
FORECAST_SAVE_INTERVAL = 300  # 5 min
_last_forecast_save: Optional[datetime] = None


def save_forecast_history(
    zone_id: str,
    forecast: List[Dict[str, Any]],
    current_score: int,
    db_path: Path = DB_PATH,
) -> int:
    """
    Persiste les prévisions d'une zone pour évaluation ultérieure.
    Throttlé à FORECAST_SAVE_INTERVAL pour éviter le bloat.
    Retourne le nombre de lignes insérées.
    """
    global _last_forecast_save
    now = datetime.now(timezone.utc)
    if _last_forecast_save and (now - _last_forecast_save).total_seconds() < FORECAST_SAVE_INTERVAL:
        return 0

    ts_now = now.isoformat(timespec="seconds")
    rows = []
    for f in forecast:
        horizon = f.get("horizon", "")
        predicted = f.get("urban_score", 0)
        # Calculer target_ts à partir du horizon string
        minutes = _horizon_to_minutes(horizon)
        if minutes is None:
            continue
        from datetime import timedelta
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


def evaluate_forecasts(
    scores: List[Dict[str, Any]],
    tolerance_minutes: int = 5,
    db_path: Path = DB_PATH,
) -> int:
    """
    Compare les forecasts passés avec les scores actuels.
    Pour chaque forecast dont target_ts est dans [now - tolerance, now + tolerance]
    et qui n'a pas encore été évalué, on enregistre le score réel et le delta.

    Retourne le nombre de forecasts évalués.
    """
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    window_start = (now - timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")
    window_end = (now + timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")

    # Scores actuels par zone
    score_map = {z["zone_id"]: z["urban_score"] for z in scores}

    sql_select = """
        SELECT id, zone_id, predicted_score
        FROM forecast_history
        WHERE target_ts >= ? AND target_ts <= ?
          AND actual_score IS NULL
    """
    sql_update = """
        UPDATE forecast_history
        SET actual_score = ?, delta = ?, evaluated_at = ?
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
            conn.execute(sql_update, (actual, delta, eval_ts, row["id"]))
            evaluated += 1

    if evaluated:
        logger.info("forecast_history : %d prévision(s) évaluée(s).", evaluated)
    return evaluated


def flag_incident_surprises(
    incident_events: Dict[str, List[Dict]],
    db_path: Path = DB_PATH,
) -> int:
    """
    Marque les forecasts évalués comme 'incident_surprise' si des incidents
    non prévus sont apparus entre ts_forecast et target_ts pour la zone.

    Logique : si un incident actif sur la zone a un starttime postérieur
    à ts_forecast, c'est un incident surprise → le delta n'est pas une erreur modèle.
    """
    if not incident_events:
        return 0

    sql_select = """
        SELECT id, zone_id, ts_forecast
        FROM forecast_history
        WHERE actual_score IS NOT NULL
          AND incident_surprise = 0
          AND ABS(delta) > 10
    """
    sql_update = "UPDATE forecast_history SET incident_surprise = 1 WHERE id = ?"

    flagged = 0
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql_select).fetchall()

        for row in rows:
            zone_events = incident_events.get(row["zone_id"], [])
            ts_fc = row["ts_forecast"]
            for ev in zone_events:
                start = ev.get("starttime", "")
                if start and start > ts_fc:
                    conn.execute(sql_update, (row["id"],))
                    flagged += 1
                    break

    if flagged:
        logger.info("forecast_history : %d prévision(s) marquée(s) incident_surprise.", flagged)
    return flagged


def get_forecast_accuracy(
    zone_id: Optional[str] = None,
    horizon: Optional[str] = None,
    limit: int = 200,
    db_path: Path = DB_PATH,
) -> Dict[str, Any]:
    """
    Retourne les stats de précision des forecasts évalués.
    - MAE global et par horizon
    - Taux d'incident_surprise
    - Dernières évaluations
    """
    where_clauses = ["actual_score IS NOT NULL"]
    params: list = []
    if zone_id:
        where_clauses.append("zone_id = ?")
        params.append(zone_id)
    if horizon:
        where_clauses.append("horizon = ?")
        params.append(horizon)

    where = " AND ".join(where_clauses)

    # Stats agrégées
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

    # Dernières évaluations
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


# ─── Internes ──────────────────────────────────────────────────────────────────

@contextmanager
def _get_conn(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_row(entry: dict[str, Any], ts_fallback: str) -> dict[str, Any]:
    """Normalise un dict score → row SQL."""
    signals     = entry.get("signals", {})       # normalisés
    raw_signals = entry.get("raw_signals", {})   # bruts ← NOUVEAU

    return {
        "ts":            entry.get("ts") or ts_fallback,
        "zone_id":       entry["zone_id"],
        # normalisés (existants)
        "traffic":       signals.get("traffic"),
        "weather":       signals.get("weather"),
        "event":         signals.get("event"),
        "transport":     signals.get("transport"),
        # bruts (nouveaux)
        "raw_traffic":   raw_signals.get("traffic"),
        "raw_weather":   raw_signals.get("weather"),
        "raw_event":     raw_signals.get("event"),
        "raw_transport": raw_signals.get("transport"),
        "raw_incident":  raw_signals.get("incident"),
        "urban_score":   entry["urban_score"],
        "level":         entry["level"],
    }