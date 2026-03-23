# ADR-010 — Clamp z négatifs traffic/transport dans RISK

**Date**: 2026-03-23
**Status**: Accepted
**Source**: Claude Code session — comparaison Google Maps vs dashboard, zones presquile/fourviere sous-scorées

## Decision
Ajouter `traffic` et `transport` à `_NEUTRAL_WHEN_LOW` : tous les signaux ont désormais leur z clampé à max(z, 0) dans `compute_risk`.

## Values
```python
_NEUTRAL_WHEN_LOW = frozenset({"weather", "event", "incident", "traffic", "transport"})
```

## Rationale
- Presquile (piéton) et Fourviere (colline) ont structurellement peu de segments Criter et une excellente desserte TCL
- Leurs z négatifs (traffic ≈ -0.4, transport ≈ -0.75) étaient amplifiés par φ(rush) ≈ 1.6 → RISK ≈ -1.2 → score ≈ 17
- Un trafic fluide ou une bonne desserte ne réduit pas la tension urbaine — au pire c'est neutre
- Après fix : score remonte au neutre ~29 (CALME), cohérent avec la réalité observée sur Google Maps

## Consequences
- ANOMALY et CONV ne sont pas affectés (utilisaient déjà max(z, 0))
- Seul RISK change : plancher à 0 pour chaque signal, pas de composante négative
- Les zones bien desservies ou calmes scorent ~29 (neutre sigmoid) au lieu de 15-24
- La détection "trafic anormalement bas" (ex: route fermée) est perdue dans RISK mais reste captée par l'absence d'anomalie

## DO NOT
- Ne pas retirer traffic/transport de `_NEUTRAL_WHEN_LOW` sans valider l'impact sur presquile et fourviere
- Ne pas modifier `compute_anomaly` — elle utilise déjà max(z, 0) indépendamment

## Triggers
Re-read when: scoring.py compute_risk, _NEUTRAL_WHEN_LOW, RISK formula, baseline calibration
