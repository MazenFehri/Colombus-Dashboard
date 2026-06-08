# Analytics & Risk Logic

## Data Sources

| Pair | Source | Notes |
|------|--------|-------|
| EUR/USD, GBP/USD | Frankfurter API | Free, reliable, business-day coverage |
| USD/TND, EUR/TND | BCT (Banque Centrale de Tunisie) scraper | HTML table scrape; weekends skipped; holidays may be missing |

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

BCT scraping misses public holidays and occasional failures, leaving calendar-day gaps in the database. A raw `pct_change()` on a gapped series would treat a 3-day return as a 1-day return, inflating volatility. Returns are normalized before any rolling calculation:

```
normalized_return = raw_return / sqrt(gap_days)
```

This rescales multi-day returns to a 1-day equivalent so the rolling standard deviation is a consistent estimator of 1-day volatility.

### Rolling 21-day std

The rolling standard deviation is computed over a 21-observation window of normalized returns. The most recent **non-zero** value is used — a flat tail (e.g. a constant scraped value repeated over several days) would otherwise mask real historical volatility.

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

## Risk Classification

Risk level is derived from the daily change percentage and the spike flag. Thresholds differ by quote currency because TND is a BCT-managed currency that moves an order of magnitude less than major pairs.

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

---

## Alert Storage

Alerts are computed on demand and persisted to the `alerts` table (one row per pair per date). Subsequent requests for the same pair+date are served from the cache without recomputation.

---

## Analysis Summary

The `/analysis/summary` endpoint aggregates across all supported pairs:

- **Most volatile** — pair with the highest `annualized_vol` (only pairs with ≥ 21 observations)
- **Most stable** — pair with the lowest `annualized_vol`
- **Biggest mover** — pair with the largest `|daily_change_pct|`
