#!/bin/sh
set -e

# Seed l'historique si la base est vide (premier démarrage ou volume vierge)
ROWS=$(python3 -c "
import sqlite3, os
try:
    c = sqlite3.connect('data/urban_signal.db')
    n = c.execute(\"SELECT COUNT(*) FROM signals_history\").fetchone()[0]
    print(n)
    c.close()
except Exception:
    print(0)
" 2>/dev/null || echo "0")

if [ "$ROWS" -lt "1000" ]; then
  echo "=== DB vide — seed historique (~90s) ==="
  python3 scripts/seed_history.py
  echo "=== Seed terminé ==="
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
