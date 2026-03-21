"""
Urban Signal Engine — Storage Service
Persistence SQLite pour signaux et scores historiques.
"""

import csv
import gzip
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "urban_signal.db"
SEED_PATH = Path(__file__).parent.parent / "data" / "seed_signals_history.csv.gz"

# Transport signal inverted around this date (old activity model → disruption model).
# Data before this timestamp uses the pre-inversion transport values.
# Adjust if inversion was deployed at a different time.
CALIBRATION_CUTOFF_TS = "2026-03-15T00:00:00"

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
    raw_incident      REAL,
    source            TEXT    DEFAULT 'live'
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

CREATE_CALIBRATION_LOG = """
CREATE TABLE IF NOT EXISTS calibration_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibrated_at   TEXT    NOT NULL,
    zone_id         TEXT,
    signal          TEXT    NOT NULL,
    old_mu          REAL,
    new_mu          REAL,
    old_sigma       REAL,
    new_sigma       REAL,
    row_count       INTEGER NOT NULL,
    cutoff_ts       TEXT    NOT NULL,
    skipped         INTEGER DEFAULT 0
);
"""

CREATE_REQUEST_LOGS = """
CREATE TABLE IF NOT EXISTS request_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    method      TEXT    NOT NULL,
    path        TEXT    NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms REAL    NOT NULL,
    client_ip   TEXT
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sh_zone_ts  ON signals_history (zone_id, ts);",
    "CREATE INDEX IF NOT EXISTS idx_sh_ts       ON signals_history (ts);",
    "CREATE INDEX IF NOT EXISTS idx_al_ts       ON alerts_log (ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_fh_target   ON forecast_history (target_ts, zone_id);",
    "CREATE INDEX IF NOT EXISTS idx_fh_zone     ON forecast_history (zone_id, ts_forecast);",
    "CREATE INDEX IF NOT EXISTS idx_rq_ts       ON request_logs (ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_rq_path_ts  ON request_logs (path, ts DESC);",
    "CREATE INDEX IF NOT EXISTS idx_rq_status   ON request_logs (status_code, ts DESC);",
]

# Migration : ajoute les colonnes raw si elles n'existent pas encore (base existante)
MIGRATE_ADD_RAW_COLUMNS = [
    "ALTER TABLE signals_history ADD COLUMN raw_traffic   REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_weather   REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_event     REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_transport REAL;",
    "ALTER TABLE signals_history ADD COLUMN raw_incident  REAL;",
    "ALTER TABLE signals_history ADD COLUMN source        TEXT DEFAULT 'live';",
    "ALTER TABLE signals_history ADD COLUMN incident_label TEXT;",
    "ALTER TABLE signals_history ADD COLUMN incident_type  TEXT;",
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
        conn.execute(CREATE_CONTACT)
        conn.execute(CREATE_CALIBRATION_LOG)
        conn.execute(CREATE_REQUEST_LOGS)
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

    # ── Passe 2 : insertion avec timestamps décalés, source='seed' ──
    cols = (
        "ts", "zone_id", "traffic", "weather", "event", "transport",
        "urban_score", "level", "raw_traffic", "raw_weather",
        "raw_event", "raw_transport", "raw_incident", "source",
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
                if c == "source":
                    values.append("seed")
                    continue
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
            if len(batch) >= 2000:
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
             urban_score, level, incident_label, incident_type)
        VALUES
            (:ts, :zone_id,
             :traffic, :weather, :event, :transport,
             :raw_traffic, :raw_weather, :raw_event, :raw_transport, :raw_incident,
             :urban_score, :level, :incident_label, :incident_type)
    """

    with _get_conn(db_path) as conn:
        conn.executemany(sql, rows)

    logger.info("save_scores_history : %d ligne(s) insérée(s).", len(rows))
    return len(rows)


# ─── Lecture ───────────────────────────────────────────────────────────────────

def get_zone_history(
    zone_id: str,
    limit: int = 200,
    source: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    where = "WHERE zone_id = ?"
    params: list = [zone_id]
    if source:
        where += " AND source = ?"
        params.append(source)
    sql = f"""
        SELECT ts, zone_id, traffic, weather, event, transport,
               raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
               urban_score, level, source
        FROM   signals_history
        {where}
        ORDER  BY ts DESC
        LIMIT  ?
    """
    params.append(limit)
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
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
) -> tuple[Optional[Dict[str, Dict[str, float]]], int]:
    """
    Calcule les baselines globales (toutes zones) depuis les raw_signals.
    Retourne (None, n) si pas assez de données (< min_count relevés).
    Retourne (baselines, n) sinon.
    Filtre : source='live' uniquement, ts >= CALIBRATION_CUTOFF_TS.
    """
    _cal_where = "AND source = 'live' AND ts >= ?"
    _cal_params: list = [CALIBRATION_CUTOFF_TS]

    sql = f"""
        SELECT COUNT(*) as n FROM signals_history
        WHERE raw_traffic IS NOT NULL {_cal_where}
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        n = conn.execute(sql, _cal_params).fetchone()["n"]

    if n < min_count:
        logger.info("Recalibration différée : %d/%d relevés qualifiés (cutoff=%s).",
                     n, min_count, CALIBRATION_CUTOFF_TS)
        return None, n

    # Sigma minimum physiquement raisonnable par signal.
    # Évite qu'un historique quasi-constant (ex: event=0.0 toujours) produise
    # sigma≈0 et des normalisations explosives.
    MIN_SIGMA = {
        "traffic":   0.15,
        "weather":   0.10,
        "event":     0.20,   # signal naturellement non-stationnaire
        "transport": 0.20,   # range [0,1] — sigma trop bas → z-scores explosifs pour zones à faible transport
        "incident":  0.15,
    }

    baselines = {}
    # event exclu : non-stationnaire (calendrier statique, peut être tout-à-zéro)
    for signal in ("traffic", "weather", "transport", "incident"):
        col = f"raw_{signal}"
        sql = f"""
            SELECT
                COUNT({col})                                      AS cnt,
                AVG({col})                                        AS mu,
                AVG({col} * {col}) - AVG({col}) * AVG({col})     AS variance
            FROM signals_history
            WHERE {col} IS NOT NULL {_cal_where}
        """
        with _get_conn(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, _cal_params).fetchone()

        if not row or row["cnt"] < 50:
            logger.warning("Calibration skip signal=%s — seulement %d relevés qualifiés.",
                           signal, row["cnt"] if row else 0)
            continue

        if row["mu"] is not None:
            variance = max(row["variance"] or 0.0, 0.0)
            sigma    = max(variance ** 0.5, MIN_SIGMA[signal])
            baselines[signal] = {
                "mu":    round(row["mu"], 4),
                "sigma": round(sigma, 4),
            }

    logger.info("Baselines recalibrées depuis %d relevés (cutoff=%s) : %s",
                n, CALIBRATION_CUTOFF_TS, baselines)
    return (baselines if baselines else None), n


def get_calibration_baselines_per_zone(
    min_count: int = 48,
    db_path: Path = DB_PATH,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Calcule les baselines par zone depuis les raw_signals.
    Retourne un dict zone_id → signal → {mu, sigma}.
    Les zones avec moins de min_count relevés sont ignorées (baseline globale utilisée).
    Le signal event est exclu (historique non-stationnaire).
    Filtre : source='live' uniquement, ts >= CALIBRATION_CUTOFF_TS.
    """
    MIN_SIGMA = {
        "traffic":   0.15,
        "weather":   0.10,
        "transport": 0.20,
        "incident":  0.15,
    }

    _cal_where = "AND source = 'live' AND ts >= ?"
    _cal_params: list = [CALIBRATION_CUTOFF_TS]

    sql = f"""
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
        WHERE raw_traffic IS NOT NULL {_cal_where}
        GROUP BY zone_id
    """

    result: Dict[str, Dict[str, Dict[str, float]]] = {}
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, _cal_params).fetchall()

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


# ─── Calibration Log ─────────────────────────────────────────────────────────

def save_calibration_log(
    entries: List[Dict[str, Any]],
    db_path: Path = DB_PATH,
) -> int:
    """
    Persiste les résultats d'une calibration dans calibration_log.
    Chaque entry : {zone_id, signal, old_mu, new_mu, old_sigma, new_sigma,
                    row_count, cutoff_ts, skipped}.
    """
    if not entries:
        return 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sql = """
        INSERT INTO calibration_log
            (calibrated_at, zone_id, signal, old_mu, new_mu,
             old_sigma, new_sigma, row_count, cutoff_ts, skipped)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows = [
        (now, e.get("zone_id"), e["signal"],
         e.get("old_mu"), e.get("new_mu"),
         e.get("old_sigma"), e.get("new_sigma"),
         e["row_count"], e["cutoff_ts"], int(e.get("skipped", 0)))
        for e in entries
    ]
    with _get_conn(db_path) as conn:
        conn.executemany(sql, rows)
    logger.info("calibration_log : %d entrée(s) insérée(s).", len(rows))
    return len(rows)


def get_calibration_log(
    limit: int = 50,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Retourne les dernières entrées du calibration_log."""
    sql = """
        SELECT calibrated_at, zone_id, signal,
               old_mu, new_mu, old_sigma, new_sigma,
               row_count, cutoff_ts, skipped
        FROM calibration_log
        ORDER BY id DESC
        LIMIT ?
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ─── Raw incident lookup ─────────────────────────────────────────────────────

def get_raw_incident_at(
    zone_id: str,
    ts: str,
    tolerance_minutes: int = 5,
    db_path: Path = DB_PATH,
) -> float:
    """
    Retourne la valeur raw_incident la plus proche de `ts` (±tolerance).
    Retourne 0.0 si aucun relevé trouvé.
    """
    ts_dt = datetime.fromisoformat(ts)
    window_start = (ts_dt - timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")
    window_end = (ts_dt + timedelta(minutes=tolerance_minutes)).isoformat(timespec="seconds")
    sql = """
        SELECT raw_incident
        FROM signals_history
        WHERE zone_id = ? AND ts >= ? AND ts <= ?
          AND raw_incident IS NOT NULL
        ORDER BY ABS(julianday(ts) - julianday(?))
        LIMIT 1
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, (zone_id, window_start, window_end, ts)).fetchone()
    return float(row["raw_incident"]) if row else 0.0


def get_active_incident_label(
    zone_id: str,
    minutes: int = 10,
    db_path: Path = DB_PATH,
) -> tuple[Optional[str], Optional[str]]:
    """
    Retourne (label, type) du dernier incident enregistré pour une zone
    dans les `minutes` dernières. (None, None) si aucun.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    sql = """
        SELECT incident_label, incident_type
        FROM signals_history
        WHERE zone_id = ? AND ts >= ? AND incident_label IS NOT NULL
        ORDER BY ts DESC
        LIMIT 1
    """
    with _get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, (zone_id, cutoff)).fetchone()
    if row:
        return row["incident_label"], row["incident_type"]
    return None, None


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


# ─── Contact ──────────────────────────────────────────────────────────────────

CREATE_CONTACT = """
CREATE TABLE IF NOT EXISTS contact_submissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL,
    email       TEXT NOT NULL,
    organisation TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def save_contact(nom: str, email: str, organisation: str, message: str, db_path: Path = DB_PATH) -> None:
    """Persiste une soumission de formulaire de contact."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO contact_submissions (nom, email, organisation, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (nom, email, organisation, message, now),
        )
    logger.info("Contact submission from %s (%s)", email, organisation)


# ─── Request logs ───────────────────────────────────────────────────────────────

def save_request_log(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: Optional[str],
    db_path: Path = DB_PATH,
) -> None:
    """Persiste un log de requête HTTP. Appelé en fire-and-forget depuis le middleware."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO request_logs (ts, method, path, status_code, duration_ms, client_ip) VALUES (?,?,?,?,?,?)",
            (now, method, path, status_code, round(duration_ms, 1), client_ip),
        )


def get_request_logs(
    limit: int = 100,
    status_code: Optional[int] = None,
    path_filter: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Retourne les logs de requêtes récents, filtrables par status et path."""
    conditions: List[str] = []
    params: List[Any] = []
    if status_code is not None:
        conditions.append("status_code = ?")
        params.append(status_code)
    if path_filter:
        conditions.append("path LIKE ?")
        params.append(f"%{path_filter}%")
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            f"SELECT ts, method, path, status_code, duration_ms, client_ip FROM request_logs WHERE {where} ORDER BY ts DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def purge_old_request_logs(days: int = 7, db_path: Path = DB_PATH) -> int:
    """Supprime les logs de requêtes plus anciens que `days` jours. Retourne le nombre de lignes supprimées."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    with _get_conn(db_path) as conn:
        cursor = conn.execute("DELETE FROM request_logs WHERE ts < ?", (cutoff,))
        deleted = cursor.rowcount
    if deleted:
        logger.info("request_logs: %d entrées purgées (>%d jours)", deleted, days)
    return deleted


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
    raw_signals = entry.get("raw_signals", {})   # bruts

    return {
        "ts":              entry.get("ts") or ts_fallback,
        "zone_id":         entry["zone_id"],
        # normalisés (existants)
        "traffic":         signals.get("traffic"),
        "weather":         signals.get("weather"),
        "event":           signals.get("event"),
        "transport":       signals.get("transport"),
        # bruts
        "raw_traffic":     raw_signals.get("traffic"),
        "raw_weather":     raw_signals.get("weather"),
        "raw_event":       raw_signals.get("event"),
        "raw_transport":   raw_signals.get("transport"),
        "raw_incident":    raw_signals.get("incident"),
        "urban_score":     entry["urban_score"],
        "level":           entry["level"],
        "incident_label":  entry.get("incident_label"),
        "incident_type":   entry.get("incident_type"),
    }