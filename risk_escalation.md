# Risk Escalation Rule

**Status:** Design — not yet implemented
**Date:** 2026-06-09
**Related:** `logic.md` (current risk logic), `research_optimization.md` (composite-index follow-on)

## Motivation

The current risk label is **single-factor**: it buckets today's `|change_pct|` against
per-quote thresholds, with a `>3σ` spike override. That misses two situations a treasurer
would call risky:

1. **A statistically abnormal move that is still small in absolute terms.** A 0.18 % TND
   move is below the 0.25 % HIGH threshold, so it reads MEDIUM at most — even if 0.18 % is a
   2.5σ event for the dinar.
2. **A normal-sized move inside a turbulent regime.** A routine 0.4 % EUR/USD day reads LOW,
   even when the pair has been swinging hard for weeks.

This is exactly the gap the `risk.py` prototype tried to close with a multi-factor score. We
adopt its **idea** — risk is more than today's move — but not its mechanism (a non-deterministic
PCA-weighted index with several bugs). Instead we keep the existing LOW / MEDIUM / HIGH label
and **escalate** it using factors we already compute. The result is deterministic, fully
explainable, and stays TND-calibrated.

---

## The rule

```
base = threshold bucket of |change_pct|          (per-quote; LOW / MEDIUM / HIGH)

if spike (z > 3σ):
    risk = HIGH                                   # unchanged from today — a spike pins HIGH

else:
    risk = base
    if (2σ ≤ z ≤ 3σ) OR (vol_regime == "elevated"):
        risk = escalate_one_level(risk)           # LOW→MEDIUM, MEDIUM→HIGH, HIGH→HIGH

# escalation is capped at ONE level regardless of how many escalators fire
# risk is never moved below base (no de-escalation)
```

Where:

- **`z`** = `|latest_normalized_return| / rolling_63d_std` — the *continuous* form of the value
  `is_spike` already computes. `is_spike` currently throws this away as a binary `> 3σ` test;
  the escalation rule reuses the `[2σ, 3σ]` band that the spike test ignores.
- **`vol_regime`** = output of `calc_vol_regime` (`elevated` / `normal` / `compressed` / `None`).
  Only `"elevated"` escalates.

### Decision tree

```
spike (z > 3σ)?
├── yes → HIGH   "Unusual spike detected (>3σ)…"
└── no  → base = bucket(|change_pct|, quote)
          │
          ├── abnormal (2σ ≤ z ≤ 3σ)?  ──┐
          ├── regime elevated?         ──┤── either true → escalate base by ONE level
          │                              │
          └── neither → risk = base ─────┘
```

---

## Inputs — all already computed

| Factor | Source | Notes |
|--------|--------|-------|
| `base` bucket | `classify_risk` per-quote thresholds | TND `0.10 / 0.25 %`, majors `0.50 / 1.00 %` |
| `z` (abnormality) | continuous form of `is_spike`'s `|return| / rolling_63d_std` | gap-normalized returns; trailing 63-day σ |
| `vol_regime` | `calc_vol_regime` | current 21d vol vs 90-obs average |

No new data sources, no new external dependencies. The only code change is threading `z` and
`vol_regime` into `classify_risk` (today it takes only `change_pct`, `spike`, `quote`).

---

## Why one level, why these thresholds

- **One-level cap.** Escalation should *nudge*, not *teleport*. Capping at one level keeps the
  signal conservative — a quiet-but-abnormal day in a turbulent regime moves LOW→MEDIUM, not
  straight to HIGH. Fewer false HIGHs, and the label stays trustworthy.
- **`2σ` floor for abnormality.** Below 2σ a move is statistically ordinary; `[2σ, 3σ]` is
  "notable but not a spike." At `> 3σ` the existing spike override already pins HIGH, so the
  band slots in cleanly beneath it with no overlap.
- **Only `elevated` regime escalates.** `normal` is the baseline; `compressed` means unusually
  calm. Neither should *raise* risk, and a calm regime must never *lower* a genuine large move —
  hence no de-escalation.

---

## Edge cases / graceful degradation

| Situation | Behaviour |
|-----------|-----------|
| < 64 observations (z unavailable) | abnormality escalator does not fire; falls back to bucket |
| < ~111 rows (`vol_regime` is `None`) | regime escalator does not fire; falls back to bucket |
| `rolling_63d_std == 0` (flat data) | z is undefined → no escalation (same guard as `is_spike`) |
| Both escalators unavailable | identical to today's pure-threshold behaviour |
| `base` already HIGH | stays HIGH (escalation capped) |

Short-history pairs and the data-start edge therefore behave **exactly as they do today** — the
rule only adds signal when the inputs exist.

---

## Worked examples

| Pair | `change_pct` | z | regime | base | Result | Why |
|------|-------------|------|--------|------|--------|-----|
| USD/TND | +0.18 % | 2.5σ | normal | MEDIUM | **HIGH** | abnormal move escalates MEDIUM→HIGH |
| USD/TND | +0.08 % | 2.4σ | normal | LOW | **MEDIUM** | small but abnormal → one bump |
| EUR/USD | +0.40 % | 1.2σ | elevated | LOW | **MEDIUM** | normal move, turbulent regime |
| EUR/USD | +0.45 % | 2.6σ | elevated | LOW | **MEDIUM** | both fire, still capped at one level |
| EUR/USD | +1.30 % | 4.1σ | elevated | HIGH | **HIGH** | spike pins HIGH directly |
| GBP/USD | +0.30 % | 1.1σ | normal | LOW | **LOW** | nothing fires — unchanged |
| EUR/TND | −0.05 % | 1.0σ | compressed | LOW | **LOW** | calm regime never lowers; nothing raises |

---

## Why this beats the alternatives

- **vs. today's single-factor label:** captures abnormal-but-small moves and turbulent regimes
  that the raw-% bucket cannot see, while keeping the same three-level output and TND calibration.
- **vs. `risk.py`'s 0–100 PCA index:** deterministic (no weights that drift as history grows),
  reproducible, and explainable in one sentence ("escalated because the move was 2.5σ"). No
  `sklearn` dependency, and the per-quote thresholds keep it correct for TND, which risk.py's
  fixed `1.5 % / 0.8 %` ceilings would not.

A continuous 0–100 *index* remains a possible future addition **if** a single rankable number is
ever needed for cross-pair sorting — but the comparison table already ranks by volatility, so it
is out of scope here (YAGNI).

---

## Implementation touch points (when built)

- `alert_engine.classify_risk` — extend signature to accept `z` and `vol_regime`; add the
  escalation step; update the message strings to name the escalation reason.
- `analytics.is_spike` / a small helper — expose the continuous `z` (not just the boolean) so
  `build_snapshot` can pass it in.
- `build_snapshot` and `/analysis/summary` — pass `z` and `vol_regime` into `classify_risk`.
- Tests — each escalation path, the one-level cap, the no-de-escalation guarantee, and the
  short-history fallbacks.
- `logic.md` — replace the single-factor description with the escalation rule.

## Out of scope

- A 0–100 composite risk index (see `research_optimization.md`).
- De-escalation / risk reduction from calm regimes.
- Changing the per-quote thresholds themselves.
