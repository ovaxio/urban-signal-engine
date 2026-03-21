# Diagnostic USE

Problème : $ARGUMENTS

## Instructions

Diagnostic structuré en 4 phases.

### Phase 1 — Localisation
Identifier d'abord le périmètre :
- **Signal suspect** ? → lire `backend/services/ingestion.py` + grep la source concernée
- **Score bizarre** ? → lire `backend/services/scoring.py` + `backend/config.py`
- **Forecast incorrect** ? → lire `backend/services/scoring.py` section forecast + `backend/services/forecast_storage.py`
- **Rapport cassé** ? → lire `backend/routers/reports.py`
- **Frontend ne charge pas** ? → lire `frontend/lib/api.ts` + le composant concerné
- **Alerte manquante/intempestive** ? → lire `backend/services/alerts.py`
- **Calibration dérivée** ? → lire `backend/services/storage.py` + `backend/services/smoothing.py`

### Phase 2 — Hypothèses
Formuler 2-3 hypothèses en ordre de probabilité :
1. [Hypothèse la plus probable] — [fichier:ligne] — [comment vérifier]
2. [Hypothèse 2] — ...
3. [Hypothèse 3] — ...

### Phase 3 — Fix
Pour chaque hypothèse validée :
1. Montrer la ligne fautive avec contexte (±5 lignes)
2. Proposer le fix minimal
3. Indiquer si un ADR est nécessaire (changement de comportement intentionnel ?)
4. Indiquer le test manuel pour valider : `GET /zones/scores`, `GET /zones/{id}/detail`, etc.

### Points de vigilance USE connus
- Transport TCL passages_tcl est INVERSÉ (ADR-001) — ne pas "corriger" l'inversion
- raw=0 → score≈29 est NORMAL (pas un bug, baseline neutral)
- Double comptage RISK+ANOMALY+CONV est INTENTIONNEL
- seed data exclue de l'EWM smoothing (source != 'live')
- CALIBRATION_CUTOFF_TS filtre les données pré-15 mars 2026

### Phase 4 — Persistance SQLite
Si le problème persiste après correction :
- Vérifier `signals_history` : `SELECT zone_id, source, timestamp, raw_traffic, raw_incident FROM signals_history ORDER BY timestamp DESC LIMIT 20;`
- Vérifier `alerts_log` : `SELECT zone_id, level, triggered_at FROM alerts_log ORDER BY triggered_at DESC LIMIT 10;`
- Vérifier `forecast_history` : `SELECT zone_id, horizon, mae, incident_surprise FROM forecast_history ORDER BY created_at DESC LIMIT 10;`
- DB path: `backend/data/urban_signal.db` — utiliser `sqlite3` ou lire via `/health`
