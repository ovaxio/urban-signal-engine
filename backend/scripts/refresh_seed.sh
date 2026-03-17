#!/bin/sh
# Régénère le fichier seed depuis la DB locale.
# Usage : sh scripts/refresh_seed.sh
#   → exporte signals_history en CSV gzippé dans data/seed_signals_history.csv.gz
#   → stage le fichier pour le prochain commit
set -e

DB="data/urban_signal.db"
SEED="data/seed_signals_history.csv.gz"

if [ ! -f "$DB" ]; then
  echo "❌ DB locale introuvable : $DB"
  exit 1
fi

ROWS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM signals_history")
echo "📦 Export signals_history ($ROWS lignes) → $SEED"

sqlite3 -header -csv "$DB" "SELECT * FROM signals_history" | gzip > "$SEED"

SIZE=$(ls -lh "$SEED" | awk '{print $5}')
echo "✅ Seed régénéré : $SEED ($SIZE, $ROWS lignes)"

# Stage automatiquement pour le prochain commit
git add "$SEED"
echo "📌 Fichier stagé pour le prochain commit"
