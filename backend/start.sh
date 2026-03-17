#!/bin/sh
set -e

# Le seed signals_history est géré automatiquement par init_db()
# au démarrage de l'app (lifespan) si la table est vide.

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
