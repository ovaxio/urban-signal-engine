"""
Urban Signal Engine — Seed historique
Génère 14 jours de données réalistes en base pour préparer la démo pitch.

Usage :
    cd backend && python scripts/seed_history.py

Principe :
  - Couvre les 14 jours précédant les premières données existantes
  - Signaux par zone avec profil phi jour/nuit, variation weekends, bruit gaussien
  - Quelques événements météo et incidents réalistes injectés
  - Utilise le vrai moteur score_all_zones → cohérence totale avec les données live
"""

import sys
import os
import random
import math
import sqlite3
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

# ── Chemin racine backend ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.scoring import score_all_zones, ZONE_NAMES
from services.storage import DB_PATH

PARIS_TZ          = ZoneInfo("Europe/Paris")
STEP_MIN          = 2       # un relevé toutes les 2 minutes (= réel)
DAYS_TO_SEED      = 14      # jours à générer

random.seed(42)

# ── Profils par zone ───────────────────────────────────────────────────────────
# Multiplicateurs appliqués au baseline global : > 1 = zone plus tendue que la moyenne

ZONE_TRAFFIC_MU = {
    "part-dieu":    1.30,   # CBD, hub principal
    "presquile":    1.20,
    "guillotiere":  1.15,
    "perrache":     1.10,
    "brotteaux":    1.05,
    "villette":     1.00,
    "gerland":      0.92,
    "montchat":     0.85,
    "fourviere":    0.82,
    "vieux-lyon":   0.90,
    "croix-rousse": 0.88,
    "confluence":   0.92,
}

ZONE_TRANSPORT_MU = {
    "part-dieu":    0.68,   # pôle d'échange majeur
    "perrache":     0.62,
    "presquile":    0.55,
    "guillotiere":  0.52,
    "brotteaux":    0.48,
    "villette":     0.45,
    "confluence":   0.45,
    "gerland":      0.42,
    "croix-rousse": 0.40,
    "vieux-lyon":   0.38,
    "montchat":     0.35,
    "fourviere":    0.30,
}

ZONE_INCIDENT_MU = {
    "part-dieu":    0.90,
    "presquile":    0.80,
    "guillotiere":  0.75,
    "perrache":     0.70,
    "brotteaux":    0.60,
    "villette":     0.65,
    "gerland":      0.60,
    "montchat":     0.50,
    "fourviere":    0.45,
    "vieux-lyon":   0.55,
    "croix-rousse": 0.55,
    "confluence":   0.55,
}

ZONE_IDS = list(ZONE_NAMES.keys())


# ── Phi (copie de scoring.py pour éviter dépendance datetime) ─────────────────

def _phi(t: float) -> float:
    """t = heure décimale Paris (0-24)."""
    def r(x, x0, x1, v0, v1):
        if x <= x0: return v0
        if x >= x1: return v1
        return v0 + (v1 - v0) * (x - x0) / (x1 - x0)
    if t < 5.0:  return 0.7
    if t < 6.5:  return r(t, 5.0,  6.5,  0.7, 1.0)
    if t < 7.0:  return r(t, 6.5,  7.0,  1.0, 1.3)
    if t < 9.5:  return 1.3
    if t < 10.5: return r(t, 9.5,  10.5, 1.3, 1.0)
    if t < 11.5: return 1.0
    if t < 12.0: return r(t, 11.5, 12.0, 1.0, 1.1)
    if t < 14.0: return 1.1
    if t < 15.0: return r(t, 14.0, 15.0, 1.1, 1.0)
    if t < 16.5: return 1.0
    if t < 17.0: return r(t, 16.5, 17.0, 1.0, 1.3)
    if t < 19.5: return 1.3
    if t < 21.0: return r(t, 19.5, 21.0, 1.3, 1.0)
    if t < 22.5: return 1.0
    return r(t, 22.5, 24.0, 1.0, 0.7)


def _noise(sigma: float) -> float:
    return random.gauss(0, sigma)


# ── Génération des signaux bruts ───────────────────────────────────────────────

def _make_signals(dt_paris: datetime, weather_val: float, incident_events: dict) -> dict:
    """Retourne signals[zone_id] = {traffic, weather, event, transport, incident}."""
    t       = dt_paris.hour + dt_paris.minute / 60.0
    phi     = _phi(t)
    weekday = dt_paris.weekday()  # 0=lundi … 6=dimanche
    weekend_factor = 0.65 if weekday >= 5 else 1.0

    signals = {}
    for zone in ZONE_IDS:
        # Trafic : baseline × phi × weekend + bruit
        traffic_base = 1.0 + (ZONE_TRAFFIC_MU[zone] - 1.0) * phi * weekend_factor
        traffic = max(0.5, min(3.0, traffic_base + _noise(0.12)))

        # Transport : suit le phi, plus fort en semaine
        transport_base = ZONE_TRANSPORT_MU[zone] * phi * weekend_factor
        transport = max(0.0, min(1.0, transport_base + _noise(0.06)))

        # Incident : faible niveau de base + spikes
        inc_base  = ZONE_INCIDENT_MU[zone] * (0.3 + 0.7 * phi)
        incident  = incident_events.get(zone, inc_base) + _noise(0.10)
        incident  = max(0.0, min(3.0, incident))

        signals[zone] = {
            "traffic":   round(traffic, 3),
            "weather":   round(weather_val, 3),
            "event":     0.0,
            "transport": round(transport, 3),
            "incident":  round(incident, 3),
        }
    return signals


# ── Événements injectés ────────────────────────────────────────────────────────

def _plan_events(start_dt: datetime, n_days: int) -> dict:
    """
    Retourne un dict ts_iso → {zone_id: incident_override}.
    Simule des incidents réalistes : accident matinal, fermeture chantier, etc.
    """
    events = {}
    rng = random.Random(99)  # seed fixe pour reproductibilité

    # Un incident majeur par semaine sur une zone aléatoire (rush matin)
    for week in range(n_days // 7 + 1):
        day_offset = week * 7 + rng.randint(0, 4)  # lundi-vendredi
        dt = start_dt + timedelta(days=day_offset)
        dt = dt.replace(hour=8, minute=rng.randint(0, 30), second=0, microsecond=0)
        zone  = rng.choice(["part-dieu", "presquile", "guillotiere", "villette"])
        level = rng.uniform(1.5, 2.8)
        # Dure 30-60 min
        for m in range(0, rng.randint(30, 60), STEP_MIN):
            key = (dt + timedelta(minutes=m)).isoformat()
            events[key] = {z: level if z == zone else None for z in ZONE_IDS}

    # Un incident soir par semaine
    for week in range(n_days // 7 + 1):
        day_offset = week * 7 + rng.randint(0, 4)
        dt = start_dt + timedelta(days=day_offset)
        dt = dt.replace(hour=17, minute=rng.randint(15, 45), second=0, microsecond=0)
        zone  = rng.choice(["perrache", "confluence", "gerland", "brotteaux"])
        level = rng.uniform(1.2, 2.2)
        for m in range(0, rng.randint(20, 45), STEP_MIN):
            key = (dt + timedelta(minutes=m)).isoformat()
            events[key] = {z: level if z == zone else None for z in ZONE_IDS}

    return events


def _plan_weather(start_dt: datetime, n_days: int) -> dict:
    """Retourne ts_iso → weather_score. 3-4 jours de pluie sur la période."""
    rng = random.Random(77)
    weather = {}
    rain_days = rng.sample(range(n_days), k=4)
    for d in rain_days:
        dt = start_dt + timedelta(days=d)
        # Pluie modérée l'après-midi
        for h in range(13, 20):
            for m in range(0, 60, STEP_MIN):
                key = dt.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()
                intensity = rng.uniform(0.5, 1.8)
                weather[key] = intensity
    return weather


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Borne de fin = première donnée existante en base (ou maintenant si vide)
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("SELECT MIN(ts) FROM signals_history").fetchone()
    conn.close()

    if row and row[0]:
        end_dt = datetime.fromisoformat(row[0])
        # Reculer d'un step pour éviter le doublon
        end_dt = end_dt - timedelta(minutes=STEP_MIN)
    else:
        end_dt = datetime.now(timezone.utc)

    start_dt = end_dt - timedelta(days=DAYS_TO_SEED)
    # Aligner sur un multiple de STEP_MIN
    start_dt = start_dt.replace(second=0, microsecond=0)

    print(f"Seed de {start_dt.isoformat()} à {end_dt.isoformat()}")

    # Pré-calcul des événements/météo
    start_paris = start_dt.astimezone(PARIS_TZ)
    incident_plan = _plan_events(start_paris, DAYS_TO_SEED)
    weather_plan  = _plan_weather(start_paris, DAYS_TO_SEED)

    total_steps = int((end_dt - start_dt).total_seconds() / 60 / STEP_MIN)
    print(f"Génération de ~{total_steps * 12:,} relevés ({total_steps} pas × 12 zones)...")

    all_rows = []
    dt = start_dt
    step = 0

    while dt <= end_dt:
        ts_iso    = dt.isoformat(timespec="seconds")
        dt_paris  = dt.astimezone(PARIS_TZ)

        # Météo du moment
        weather_val = weather_plan.get(
            dt_paris.replace(second=0, microsecond=0).isoformat(),
            0.05 + _noise(0.03)  # très légère valeur de base (soleil)
        )
        weather_val = max(0.0, weather_val)

        # Incidents du moment
        inc_ev_map  = incident_plan.get(ts_iso, {})
        inc_map     = {}
        for z in ZONE_IDS:
            v = inc_ev_map.get(z)
            if v is not None:
                inc_map[z] = v

        signals = _make_signals(dt_paris, weather_val, inc_map)
        scores  = score_all_zones(signals, dt=dt)

        for s in scores:
            raw = signals[s["zone_id"]]
            all_rows.append({
                "ts":            ts_iso,
                "zone_id":       s["zone_id"],
                "traffic":       round(s["signals"].get("traffic", 0), 4),
                "weather":       round(s["signals"].get("weather", 0), 4),
                "event":         round(s["signals"].get("event", 0), 4),
                "transport":     round(s["signals"].get("transport", 0), 4),
                "raw_traffic":   raw["traffic"],
                "raw_weather":   raw["weather"],
                "raw_event":     raw["event"],
                "raw_transport": raw["transport"],
                "raw_incident":  raw["incident"],
                "urban_score":   s["urban_score"],
                "level":         s["level"],
            })

        dt   += timedelta(minutes=STEP_MIN)
        step += 1
        if step % 500 == 0:
            pct = step / total_steps * 100
            print(f"  {pct:.0f}% — {step}/{total_steps} pas, {len(all_rows):,} lignes...")

    # Insertion en batch
    print(f"Insertion de {len(all_rows):,} lignes en base...")
    sql = """
        INSERT INTO signals_history
            (ts, zone_id, traffic, weather, event, transport,
             raw_traffic, raw_weather, raw_event, raw_transport, raw_incident,
             urban_score, level, source)
        VALUES
            (:ts, :zone_id, :traffic, :weather, :event, :transport,
             :raw_traffic, :raw_weather, :raw_event, :raw_transport, :raw_incident,
             :urban_score, :level, 'seed')
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executemany(sql, all_rows)
    conn.commit()
    conn.close()

    print(f"✓ Seed terminé. {len(all_rows):,} lignes insérées.")

    # Vérification rapide
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT MIN(ts), MAX(ts), COUNT(*) FROM signals_history"
    ).fetchone()
    conn.close()
    print(f"  Base : {row[2]:,} lignes total | {row[0][:10]} → {row[1][:10]}")


if __name__ == "__main__":
    main()
