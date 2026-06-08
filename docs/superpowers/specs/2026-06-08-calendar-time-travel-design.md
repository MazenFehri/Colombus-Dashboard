# Calendar Time-Travel — Design Spec

**Date:** 2026-06-08
**Status:** Approved (design), pending spec review

## Goal

Add a date calendar to the dashboard. Selecting a date re-anchors the page to that
historical "as-of" date: KPIs, chart, risk, and the cross-pair Comparison Table all
reflect the selected date. The AI Market Intelligence card stays live (today). A
"Live / Today" control returns the page to the present.

## Decisions (from brainstorming)

1. **Time-travel the whole dashboard** — not just a lookup panel.
2. **Weekends disabled in the picker.** A clicked holiday (a weekday with no data)
   falls back server-side to the nearest prior trading day, shown with a small note.
3. **Everything except AI follows the date** — KPIs, chart, risk, Comparison Table
   move to the as-of date; AI commentary stays live.
4. Date range bounded to the available data: **2020-04-09 → today**.

## Approach

A single consolidated **snapshot endpoint** computes the full per-pair analysis as of
a given date server-side. This matches the frontend's existing `PairAnalysis` shape
(which today is assembled from six separate calls) and centralises all "as-of" window
math in one tested place. It also fixes a pre-existing gap: the `performance` endpoint
currently has no date parameter and always ends at today.

---

## Backend

### `analytics.build_snapshot(df, as_of) -> dict`

New function in `app/services/analytics.py`. Given a rate DataFrame and a target date:

1. **Resolve the as-of date.** Take the latest row with `date <= as_of`. That row's
   date is `resolved_date` (handles holidays). If no row ≤ as_of exists, raise
   `ValueError`.
2. Slice the DataFrame to `date <= resolved_date` and compute, reusing existing helpers:
   - `rate` — rate on `resolved_date`
   - `d1` — `calc_daily_change` on the sliced df (None if < 2 rows)
   - `d7` / `d30` — `calc_performance(..., "weekly")` / `("monthly")` on the sliced df
   - `high` / `low` — `calc_high_low` over the 30 days ending at `resolved_date`
   - `volatility` — `calc_volatility` on the sliced df (None if < 21 days of history)
   - `risk` — `classify_risk(d1, spike=is_spike(slice), quote=quote)` when `d1` is
     available, else `"LOW"`
3. Return a dict with all fields plus `resolved_date`. Fields that lack enough history
   (e.g. `volatility`, `d30` near the 2020 data start) are returned as `None`.

The function takes the already-loaded df so it stays pure and unit-testable.

### Endpoint: `GET /analysis/{base}/{quote}/snapshot`

In `app/routers/analysis.py`.

- Query param `as_of: date` — optional, defaults to today (live).
- Validates the pair (`_validate_pair`), ensures rates are cached for a window wide
  enough to cover volatility/30-day math (≈400 calendar days ending at `as_of`),
  loads the df, and calls `build_snapshot`.
- Response schema `SnapshotOut`:

```
SnapshotOut:
  resolved_date: date
  rate:        float          # always present (requires ≥1 row ≤ as_of)
  d1:          float | null   # null if no prior trading day exists (data-start edge)
  d7:          float | null
  d30:         float | null
  high:        float
  low:         float
  volatility:  float | null   # rolling_21d_std (daily), as the frontend expects
  risk:        str            # LOW | MEDIUM | HIGH
```

- `risk` is computed from `d1` (+ spike) when `d1` is available; if `d1` is `null`
  (insufficient history), `risk` defaults to `"LOW"` (no movement can be assessed).
- `422` if there is no data at or before `as_of` (only reachable via direct API use;
  the picker prevents it in the UI).

### Notes

- Existing per-metric endpoints (`daily-change`, `performance`, `high-low`,
  `volatility`, `alert`) are left in place for direct/other use; the dashboard moves to
  the snapshot endpoint.
- `volatility` is returned as the daily `rolling_21d_std` to match the frontend's
  current expectation (`vol.rolling_21d_std * 100`).

---

## Frontend

### Data layer

- `endpoints.ts`: add `snapshot(b, q, asOf?)` →
  `/analysis/{b}/{q}/snapshot` with optional `?as_of=YYYY-MM-DD`.
- `client.ts`: `fetchPairAnalysis(pair, asOf?)` calls the snapshot endpoint in a single
  request (replacing the current six-call fan-out). Returns the existing `PairAnalysis`
  shape extended with `resolvedDate: string`.

### State & controls

- `App.tsx` holds `asOf: string | null` (null = live/today).
- A **DatePicker** control (new `components/DatePicker.tsx` or a small library) above the
  KPI grid:
  - `min = 2020-04-09`, `max = today`
  - Weekends disabled.
  - A **"Live / Today"** button clears `asOf` back to null.
- `asOf` is threaded into `KpiCards`, `RateChart`, `RiskBadge`, `ComparisonTable` via the
  React Query key so each refetches when the date changes:
  `useQuery(['analysis', pair, asOf], () => fetchPairAnalysis(pair, asOf))`.
- `MarketIntelligence` is **not** given `asOf` — it stays live.

### As-of presentation

- When `asOf` is set, show an "As of {resolved_date}" badge near the top.
- When `resolved_date` ≠ the picked date (holiday fallback), append a subtle note:
  "nearest trading day".
- `RateChart` shows its trailing window **ending at** `resolved_date` instead of today.

---

## Edge cases

| Case | Behaviour |
|------|-----------|
| Weekend picked | Not possible — disabled in picker. |
| Holiday picked (weekday, no data) | Server resolves to nearest prior trading day; UI notes it. |
| Date < data start | Picker min-bounds at 2020-04-09. |
| Insufficient history for d30 / volatility | Field returned as `null`; UI renders "—". |
| `as_of` in the future / today | Treated as live (latest available row). |

---

## Testing

**Backend (`tests/test_analytics.py`, `tests/test_analysis.py`):**
- `build_snapshot` on a mid-history date returns all fields populated and the correct
  `resolved_date`.
- `build_snapshot` on a date with < 21 days of prior history returns `volatility = None`
  (and `d30 = None` where applicable).
- `build_snapshot` on a holiday (a weekday absent from the df) returns the prior trading
  day as `resolved_date`.
- Endpoint test: `GET .../snapshot?as_of=YYYY-MM-DD` returns 200 with the schema;
  omitting `as_of` returns the live snapshot.

**Frontend:**
- `fetchPairAnalysis` issues one request and maps the snapshot to `PairAnalysis`.
- Changing `asOf` re-keys the queries and refetches; "Live" resets to null.

---

## Out of scope

- Spot-vs-forward recommendation (tracked separately in `forward_spot.md`).
- AI commentary for historical dates (stays live by decision 3).
- Holiday calendar pre-computation in the picker (we rely on server-side fallback).
