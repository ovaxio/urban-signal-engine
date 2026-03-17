"""
Urban Signal Engine — Storage Service
Persistence SQLite pour signaux et scores historiques.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "urban_signal.db"

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

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sh_zone_ts  ON signals_history (zone_id, ts);",
    "CREATE INDEX IF NOT EXISTS idx_sh_ts       ON signals_history (ts);",
    "CREATE INDEX IF NOT EXISTS idx_al_ts       ON alerts_log (ts DESC);",
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
        for idx_sql in CREATE_INDEXES:
            conn.execute(idx_sql)
        _migrate_raw_columns(conn)

    logger.info("DB initialisée : %s", db_path)


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
    # Signaux exclus de la calibration automatique :
    # - event : non-stationnaire (calendrier statique, peut être tout-à-zéro)
    # - traffic : le seed génère des ratios ~1.0 (flux libre) ≠ TomTom réel (~1.95)
    #   → la calibration corrompt mu et fait exploser les z-scores (+5σ pour trafic normal)
    for signal in ("weather", "transport", "incident"):
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
    # traffic exclu : le seed génère des ratios ~1.0 ≠ TomTom réel (~1.95)
    # → calibration par zone corromprait mu et ferait exploser les z-scores
    MIN_SIGMA = {
        "weather":   0.10,
        "transport": 0.10,
        "incident":  0.15,
    }

    sql = """
        SELECT
            zone_id,
            COUNT(raw_traffic)                                                AS n,
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
        for signal in ("weather", "transport", "incident"):
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