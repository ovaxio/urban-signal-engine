#!/bin/sh
# Régénère le fichier seed + snapshot de calibration depuis la DB locale.
# Usage : sh scripts/refresh_seed.sh
#   → exporte signals_history en CSV gzippé dans data/seed_signals_history.csv.gz
#   → exporte les baselines calibrées dans data/calibration_snapshot.json
#   → stage les fichiers pour le prochain commit
set -e

DB="data/urban_signal.db"
SEED="data/seed_signals_history.csv.gz"
SEED_FORECAST="data/seed_forecast_history.csv.gz"
SNAPSHOT="data/calibration_snapshot.json"

if [ ! -f "$DB" ]; then
  echo "DB locale introuvable : $DB"
  exit 1
fi

ROWS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM signals_history")
echo "Export signals_history ($ROWS lignes) -> $SEED"

sqlite3 -header -csv "$DB" "SELECT * FROM signals_history" | gzip > "$SEED"

SIZE=$(ls -lh "$SEED" | awk '{print $5}')
echo "Seed regenere : $SEED ($SIZE, $ROWS lignes)"

# Forecast history
FC_ROWS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM forecast_history")
echo "Export forecast_history ($FC_ROWS lignes) -> $SEED_FORECAST"
sqlite3 -header -csv "$DB" "SELECT * FROM forecast_history" | gzip > "$SEED_FORECAST"
FC_SIZE=$(ls -lh "$SEED_FORECAST" | awk '{print $5}')
echo "Seed forecast regenere : $SEED_FORECAST ($FC_SIZE, $FC_ROWS lignes)"

# Calibration snapshot (ADR-015)
echo "Export calibration snapshot -> $SNAPSHOT"
cd "$(dirname "$0")/.."
python -c "
from services.storage import export_calibration_snapshot
result = export_calibration_snapshot()
if result:
    print(f'Snapshot exporte : {result}')
else:
    print('Snapshot export skipped (donnees insuffisantes)')
"
cd - > /dev/null

# Stage automatiquement pour le prochain commit
git add "$SEED" "$SEED_FORECAST"
if [ -f "$SNAPSHOT" ]; then
  git add "$SNAPSHOT"
fi
echo "Fichiers stages pour le prochain commit"
