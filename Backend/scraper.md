cont# BCT Scraper & TND Historical Data — Design Spec

## Purpose

Provide accurate, historically-grounded USD/TND and EUR/TND exchange rate data to:

1. Power the live dashboard with real BCT interbank rates
2. Feed the AI commentary layer with enough historical depth (Apr 2020 → present) to produce **realistic risk interpretations** — trend analysis, regime detection, volatility context — that a client can act on

Without this data, the AI layer has no baseline to judge whether today's rate is unusual, expensive, or risky.

---

## Data Sources

| Pair | Source | Notes |
|------|--------|-------|
| EUR/USD | Frankfurter v2 | Unchanged |
| GBP/USD | Frankfurter v2 | Unchanged |
| USD/TND | CSV (history) + BCT scraper (recent/live) | BCT interbank rate |
| EUR/TND | CSV (history, derived) + BCT scraper (recent/live) | Derived in CSV; direct from BCT |

---

## CSV Historical Seed (Apr 2020 → Jan 2026)

**File:** `Backend/USDTNDEURTND.csv`

**Format:**
- Date column: `DD/MM/YYYY` (e.g. `9/4/2020`)
- Column 2 header `EUR/TND` — actual values (~1.09–1.20) are EUR/USD cross rates
- Column 3 header `USD/TND` — correct USD/TND values (~2.87–2.92)
- Trailing empty columns — must be ignored

**Derivation:**
- `USD/TND_stored = col3` (direct)
- `EUR/TND_stored = col2 × col3` (EUR/USD × USD/TND = EUR/TND)

**Script:** `scripts/seed_tnd_rates.py`
- Reads CSV, parses dates, computes EUR/TND
- Upserts into `exchange_rates` table with `source="csv"`
- Idempotent — safe to re-run

---

## BCT Scraper

**Target:** `https://www.bct.gov.tn/bct/siteprod/cours.jsp?date=YYYYMMDD&la=AN`

**Module:** `app/services/bct.py`

### Interface

```python
fetch_rates(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]
```

Loops `from_date` to `to_date` day by day, skipping weekends. For each date:
1. GET `cours.jsp?date=YYYYMMDD&la=AN`
2. Parse HTML with `pd.read_html()` — find table containing a `Sigle` column
3. Filter row where `Sigle == base` (e.g. `"USD"` or `"EUR"`)
4. Read `Valeur` cell — replace comma with dot, convert to float
5. On any failure (weekend, holiday, HTTP error) — skip that date silently

### Gap fill on first request

The CSV covers up to Jan 2026. The BCT scraper fills Feb 2026 → today (~110 working days) on first request. This is a one-time cost; all results are cached in the DB so subsequent calls are instant.

---

## Routing

**Updated in:** `app/routers/rates.py` — `_ensure_rates_cached`

```
if (base, quote) in {("USD", "TND"), ("EUR", "TND")}:
    source = bct.fetch_rates(...)
else:
    source = frankfurter.fetch_rates(...)
```

---

## Dependency

Add to `requirements.txt`:
```
lxml>=5.0
```

Required by `pandas.read_html()` for HTML parsing.

---

## AI Layer Context

The AI commentary service (`app/services/ai_service.py`) uses exchange rate history to:
- Identify whether a rate movement is within normal historical variance or a genuine outlier
- Anchor risk levels to real multi-year context (e.g. "USD/TND has traded between 2.87–3.10 since 2020 — today's rate of 3.05 is near the upper bound")
- Detect regime changes (sustained TND depreciation vs. temporary spike)
- Give the client actionable, contextually grounded assessments rather than generic commentary

Without deep history, the AI can only describe today — with it, it can interpret and advise.

---

## File Changes Summary

| File | Change |
|------|--------|
| `app/services/bct.py` | New — BCT scraper |
| `scripts/seed_tnd_rates.py` | New — CSV import |
| `app/routers/rates.py` | Update `_ensure_rates_cached` routing |
| `requirements.txt` | Add `lxml>=5.0` |
| `app/services/frankfurter.py` | No change (Frankfurter v2 already set) |
