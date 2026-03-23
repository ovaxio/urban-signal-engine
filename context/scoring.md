# Scoring Engine — context/scoring.md

Loaded for: score, signal, weight, calibration, phi, forecast, ingestion, anomaly, risk, spread.
Invoke `scoring-guardian` (subagent_type) before any HIGH RISK change.

## UrbanScore formula (0-100)
```
score = sigmoid(alert + λ₄·spread) × 100
  alert  = λ₁·RISK + λ₂·ANOMALY + λ₃·CONV
  spread = K · Σ max(alert_neighbor, 0)
```
Sigmoid centered at raw=1.5 (k=0.6):
- raw=0 → score≈29 (CALME — neutral baseline, NOT 0)
- raw=1.5 → score=50 (median tension)
- raw=3.0 → score≈71 (CRITIQUE threshold)

## Score levels
- 0-34: CALME — normal operation
- 35-54: MODERE — weak signals, attention recommended
- 55-71: TENDU — confirmed tension, active monitoring
- 72-100: CRITIQUE — converging strong signals

## Components
- **RISK** = φ(t) × Σ(wₛ × max(zₛ, 0)) — weighted risk, z clamped ≥0 (ADR-010)
- **ANOMALY** = Σ(αₛ × max(zₛ, 0)) — peak detection (ReLU, positive only)
- **CONV** = min(Σ(βₖ × gate(zₐ) × gate(zᵦ)), 2.0) — signal convergence
- **SPREAD** = K × Σ max(alert_neighbor, 0) — spatial contagion (not relief)
- **φ(t)** = temporal profile (semaine, mercredi, vacances, weekend)

Double counting (RISK + ANOMALY + CONV) is intentional — each captures a different aspect.

## 5 signals (config.py)
| Signal    | Weight | Source                              | Range     |
|-----------|--------|-------------------------------------|-----------|
| traffic   | 0.35   | Grand Lyon Criter WFS (V/O/R/N)    | 0.5 – 3.0 |
| incident  | 0.25   | Criter events + TomTom incidents    | 0.0 – 3.0 |
| transport | 0.15   | TCL parcrelais + passages + Velo'v  | 0.0 – 1.0 |
| weather   | 0.15   | Open-Meteo (precip + wind + WMO)    | 0.0 – 3.0 |
| event     | 0.10   | Static 2026 calendar                | 0.0 – 3.0 |

## Transport signal composition (ingestion.py)
```
parcrelais × 0.30 + passages_tcl × 0.50 + velov × 0.20
```
passages_tcl is INVERTED: `1.0 - min(count / seuil, 1.0)` (fewer buses = more tension).

## EWM smoothing (smoothing.py)
α=0.4, window=6 rows, reads raw_* columns from signals_history.
Only applies to source='live' rows (excludes seed data).

## Calibration (main.py)
Auto-recalibration weekly at 3:00 AM Paris time from raw_signals history.
Per-zone baselines override global baseline. Event signal excluded (non-stationary).

## Forecast model (scoring.py)
- Short horizons (30/60/120 min): weighted average of 3 scenarios (ADR-012)
  - Persistence (decay), maintained situation (φ ratio), Criter projection
- Extended horizons (6/12/24h): structural model
  - Historical profiles + weather forecast + persistent incidents (decay, ADR-013) + φ(t)
- Accuracy tracked: forecast_history table with MAE per horizon, incident_surprise flags (ADR-014)
