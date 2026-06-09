# Analytics & Risk Logic

## Data Sources

| Pair | Source | Notes |
|------|--------|-------|
| EUR/USD, GBP/USD, USD/TND, EUR/TND | Frankfurter API (v2 `/rates`) | Free, reliable, business-day coverage; full TND history back to ~2000 |

All four pairs now come from **Frankfurter v2** (`https://api.frankfurter.dev/v2/rates`). The earlier BCT (Banque Centrale de Tunisie) HTML scraper and the CSV seed were removed once Frankfurter v2 was confirmed to provide continuous, aligned TND history. A single-date `fawazahmed` lookup remains only as a last-resort fallback.

Data is fetched on demand and cached in the database. A range is re-fetched only when fewer than 80% of expected business days are present.

---

## Daily Change

Computed as the percentage difference between the two most recent observations:

```
change_pct = (rate[today] - rate[yesterday]) / rate[yesterday] * 100
```

Requires at least 2 data points. Returns the raw rate, previous rate, and rounded percentage.

---

## Volatility

### Normalization for data gaps

Markets are closed on weekends and public holidays, leaving calendar-day gaps in the database. A raw `pct_change()` on a gapped series would treat a 3-day return (e.g. across a weekend) as a 1-day return, inflating volatility. Returns are normalized before any rolling calculation:

```
normalized_return = raw_return / sqrt(gap_days)
```

This rescales multi-day returns to a 1-day equivalent so the rolling standard deviation is a consistent estimator of 1-day volatility.

### Rolling 21-day std

The rolling standard deviation is computed over a 21-observation window of normalized returns. The most recent **non-zero** value is used — a flat tail (a constant rate repeated over several days) would otherwise mask real historical volatility.

### Annualized volatility

```
annualized_vol = rolling_21d_std * sqrt(252)
```

252 is the conventional number of trading days per year.

### Minimum data requirement

At least 21 observations are required. Fewer than 21 returns `None` (shown as "–" in the UI).

---

## Spike Detection

A spike is flagged when the latest normalized daily return exceeds 3 standard deviations of the trailing 63-day window:

```
is_spike = |latest_return| > 3 * rolling_63d_std
```

Requirements:
- At least 64 observations in the loaded window
- At least 63 normalized returns after gap-normalization
- `sigma > 0` (a zero sigma means completely flat data — no spike possible)

If any requirement is unmet, `is_spike` returns `False`.

---

## Directional & Regime Signals

These are computed alongside the risk metrics (in `build_snapshot`, so they are **time-travel aware**) and surfaced as UI badges and as context for the AI commentary. They are **interpretation aids — not inputs to the risk label**.

### Trend (MA7 vs MA30)

```
ma7  = mean(last 7 rates)
ma30 = mean(last 30 rates)
neutral  if |ma7 - ma30| / ma30 < 0.001
bullish  if ma7 > ma30
bearish  if ma7 < ma30
```

Requires ≥ 30 rows; `None` otherwise (and `None` if either MA is NaN).

### Volatility regime

Compares the **current** 21-day rolling volatility to the average of that rolling series over the last 90 observations:

```
elevated    if current > 1.5 × avg90
compressed  if current < 0.6 × avg90
normal      otherwise
```

Requires ≥ 90 rolling-std observations (≈ 111 input rows); `None` otherwise. Returns `None` on a flat/zero current window (treated as a data artifact, consistent with the volatility calc).

### Momentum

Acceleration of the daily return — is the move speeding up or reversing?

```
momentum = (return_today - return_yesterday) / |return_yesterday|
```

Requires ≥ 3 rows; `None` if yesterday's return is ~0.

---

## Risk Classification

Risk level is a **single-factor classifier** — it is derived from the daily change percentage and the spike flag only. Trend, volatility, and the regime signals above are shown as context but do **not** change the risk label. Thresholds differ by quote currency because TND is a managed currency that moves an order of magnitude less than major pairs.

### Thresholds

| Quote | LOW | MEDIUM | HIGH |
|-------|-----|--------|------|
| TND | < 0.10 % | 0.10 – 0.25 % | ≥ 0.25 % |
| USD (majors) | < 0.50 % | 0.50 – 1.00 % | ≥ 1.00 % |

### Spike override

A confirmed spike (`is_spike = True`) always produces **HIGH** risk, regardless of the daily change percentage.

### Decision tree

```
is_spike?
├── yes → HIGH  "Unusual spike detected (>3σ)…"
└── no  → check |change_pct| against thresholds for quote currency
          ├── < low_thresh  → LOW    "Normal movement…"
          ├── < high_thresh → MEDIUM "Moderate movement…"
          └── ≥ high_thresh → HIGH   "Significant movement…"
```

### Why separate TND thresholds?

The TND is a managed/pegged currency controlled by the BCT. Typical daily moves are 0.01–0.15 %, vs. 0.3–1 % for EUR/USD or GBP/USD. Using major-pair thresholds for TND would cause it to permanently read LOW, making the risk signal meaningless for Tunisian dinar exposure.

### Consistency across surfaces

The same `classify_risk(change_pct, spike, quote)` is used everywhere the risk appears — the snapshot/badge, the `/analysis/summary` table, and the **AI commentary**. The `quote` argument is passed in every path so the per-quote thresholds always apply (previously the AI commentary omitted `quote`, mislabeling TND risk against major-pair thresholds — now fixed).

### Composite risk index — evaluated, deferred

A multi-factor risk *index* (blending daily shock + volatility regime + an abnormality/z-score into one number) was prototyped (`risk.py`) and evaluated. It captured a good idea — risk as more than today's move — but had defects: a broken PCA weighting, no return value, EUR/USD-scaled ceilings that under-score TND, and a non-deterministic score that drifts as history grows. It was **not adopted**. A distilled, deterministic version (fixed weights, per-quote scaling) is recorded as a follow-on in `research_optimization.md`; the prototype file has been removed. The current label remains the single-factor classifier above.

---

## Alert Storage

Alerts are computed on demand and persisted to the `alerts` table (one row per pair per date). Subsequent requests for the same pair+date are served from the cache without recomputation.

---

## Analysis Summary

The `/analysis/summary` endpoint aggregates across all supported pairs:

- **Most volatile** — pair with the highest `annualized_vol` (only pairs with ≥ 21 observations)
- **Most stable** — pair with the lowest `annualized_vol`
- **Biggest mover** — pair with the largest `|daily_change_pct|`
