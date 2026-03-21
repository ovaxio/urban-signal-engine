# Validation d'un changement scoring USE

Changement demandé : $ARGUMENTS

## Instructions

Invoquer l'agent `scoring-guardian` (subagent_type: scoring-guardian) pour évaluer ce changement.
L'agent lira les fichiers nécessaires (`config.py`, `scoring.py`, `smoothing.py`, `storage.py`, ADRs 001-003),
classifiera le risque (HIGH / MEDIUM / LOW), et produira une recommandation GO / NO-GO avec diff exact.

> **HIGH RISK** : tout changement sur WEIGHTS, sigmoid, λ/α/β/θ, EWM, ou calibration
> requiert une **confirmation explicite de l'utilisateur** avant modification.
