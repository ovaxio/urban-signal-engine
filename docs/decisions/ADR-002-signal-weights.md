# ADR-002 — Signal weights
Date: 2026-03-12 | Status: Accepted | Source: Claude.ai research (CityPulse, INRIX, TomTom)
## Decision
Signal weights set from 5-benchmark consensus. Traffic dominates. Transport reduced to 0.15.
## Values (immutable until explicitly changed)
- **traffic: 0.35** | **incidents: 0.25** | **transport: 0.15** | **weather: 0.15** | **events: 0.10**
- Transport sub-weights: **parcrelais: 0.30** | **passages_tcl: 0.55** (inverted, ADR-001) | **velov: 0.15**
- LAMBDA: l1=0.45, l2=0.35, l3=0.20, l4=0.15
- Sigmoid: center=1.5, k=0.6 — neutral ~29, median=50, CRITIQUE ~72
## Rationale
- Traffic #1 in all 5 benchmarks. Transport reduced from 0.25 (no benchmark supports 25% for transit)
- Weather/events raised for collectivites/insurer credibility. Sum=1.0 enforced at startup.
## Consequences
- Weights are constants in config.py — no runtime mutation path exists
- Any weight change requires manual validation on 50+ ground-truth events
## DO NOT
- Auto-adjust weights at runtime (no gradient updates, no feedback loops)
- Change weights without 50+ ground-truth events. Restore transport to 0.25.
- Add ML-based weight optimization at MVP stage
## Triggers
Re-read when: WEIGHTS in config.py/scoring.py, signal weight discussion, new segment evaluation
