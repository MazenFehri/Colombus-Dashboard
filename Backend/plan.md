# FX Risk Alert & Currency Dashboard — Backend Implementation Plan

## Context

This is a Remote Intern Challenge to build an FX Risk Alert & Currency Dashboard. The system monitors exchange rates, computes volatility, and alerts users to currency risk. The backend must expose a REST API consumed by a frontend dashboard.

**Research already done:** Frankfurter API (api.frankfurter.dev) is the primary data source — no registration required, covers EUR/USD, GBP/USD, USD/TND, EUR/TND back to 1999. fawazahmed0 CDN is the fallback.

**Stack chosen:**
- Framework: FastAPI (Python)
- Database: SQLite via SQLAlchemy ORM
- AI: Groq API — `llama3-70b-8192` (free tier)
- Data fetch strategy: On-demand (fetch from Frankfurter on request, cache in SQLite)

---

## Project Structure

```
backend/
├── app/
│   ├── main.py               # App factory, CORS, router registration, lifespan
│   ├── database.py           # SQLite engine, SessionLocal, get_db dependency
│   ├── models.py             # SQLAlchemy ORM table definitions
│   ├── schemas.py            # Pydantic request/response models
│   ├── config.py             # Settings via pydantic-settings (.env loading)
│   ├── routers/
│   │   ├── currencies.py     # GET /api/v1/currencies
│   │   ├── rates.py          # GET /api/v1/rates/**
│   │   ├── alerts.py         # GET /api/v1/alerts/**
│   │   ├── analysis.py       # GET /api/v1/analysis/summary
│   │   └── ai.py             # POST /api/v1/ai/commentary
│   └── services/
│       ├── frankfurter.py    # Frankfurter API client + fawazahmed0 fallback
│       ├── analytics.py      # pandas-based volatility, performance, high/low
│       ├── alert_engine.py   # Risk level classification (low/medium/high)
│       └── ai_service.py     # Groq llama3-70b-8192 client + prompt builder
├── scripts/
│   └── seed_currencies.py    # Populate currencies table on first run
├── tests/
│   ├── test_rates.py
│   ├── test_analytics.py
│   └── test_alerts.py
├── requirements.txt
├── .env                      # GROQ_API_KEY, DATABASE_URL
└── README.md
```

---

## Database Schema

### Table: `currencies`
```sql
CREATE TABLE currencies (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,   -- "USD", "EUR", "GBP", "TND"
    name TEXT NOT NULL           -- "US Dollar"
);
```
Seeded once at startup via `scripts/seed_currencies.py`.

### Table: `exchange_rates`
```sql
CREATE TABLE exchange_rates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency  TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate           REAL NOT NULL,
    date           DATE NOT NULL,
    source         TEXT NOT NULL DEFAULT 'frankfurter',
    UNIQUE(base_currency, quote_currency, date)
);
```
- On-demand fetches upsert here. The UNIQUE constraint prevents duplicate rows on re-fetch.
- All analytics read from this table using pandas.

### Table: `alerts`
```sql
CREATE TABLE alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency    TEXT NOT NULL,
    quote_currency   TEXT NOT NULL,
    date             DATE NOT NULL,
    risk_level       TEXT NOT NULL,  -- "low", "medium", "high"
    daily_change_pct REAL NOT NULL,
    message          TEXT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
- Written every time `/alerts/{base}/{quote}` is called for a new date.
- Enables alert history via `/alerts/{base}/{quote}/history`.

### Table: `ai_commentary`
```sql
CREATE TABLE ai_commentary (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency  TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    date           DATE NOT NULL,
    commentary     TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
- One row per (base, quote, date). Cached — repeated POST for same date returns stored value.

---

## API Endpoints

All routes prefixed with `/api/v1`.

### Currencies
| Method | Path | Response |
|--------|------|----------|
| GET | `/currencies` | `[{ code, name }]` |

### Rates
| Method | Path | Query Params | Response |
|--------|------|-------------|----------|
| GET | `/rates/{base}/{quote}` | `from_date`, `to_date` | `[{ date, rate }]` — triggers on-demand fetch |
| GET | `/rates/{base}/{quote}/daily-change` | `date` (default: latest in DB) | `{ date, rate, prev_rate, change_pct }` |
| GET | `/rates/{base}/{quote}/performance` | `period=weekly\|monthly` | `{ period, start_date, end_date, start_rate, end_rate, change_pct }` |
| GET | `/rates/{base}/{quote}/high-low` | `from_date`, `to_date` | `{ high, high_date, low, low_date }` |
| GET | `/rates/{base}/{quote}/volatility` | `from_date`, `to_date` | `{ rolling_21d_std, annualized_vol, latest_date }` |

### Alerts
| Method | Path | Query Params | Response |
|--------|------|-------------|----------|
| GET | `/alerts/{base}/{quote}` | `date` (default: latest in DB) | `{ date, risk_level, daily_change_pct, message }` |
| GET | `/alerts/{base}/{quote}/history` | `from_date`, `to_date` | `[{ date, risk_level, daily_change_pct, message }]` |

### Analysis
| Method | Path | Response |
|--------|------|----------|
| GET | `/analysis/summary` | `{ most_volatile, most_stable, biggest_mover, pairs: [...] }` |

### AI Commentary
| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/ai/commentary` | `{ base, quote, date }` | `{ commentary, date, cached }` |

---

## On-Demand Fetch Flow

All `/rates/*` endpoints trigger this logic before returning:

```
1. Parse requested date range
2. Query exchange_rates table for existing rows in range
3. Find missing dates (gaps between requested range and cached rows)
4. If gaps exist:
   a. Call Frankfurter API: GET /v2/rates?from=X&to=Y&base={base}&quotes={quote}
   b. On failure → call fawazahmed0 CDN fallback
   c. On both fail → raise HTTP 503
   d. On success → bulk upsert into exchange_rates (INSERT OR REPLACE)
5. Re-query DB for full range → return to caller
```

This means:
- First request for EUR/USD Jan–Dec 2024 hits Frankfurter once
- All subsequent requests for any subset of that range return from SQLite instantly

---

## Analytics Calculations (`services/analytics.py`)

All use pandas DataFrames loaded from `exchange_rates`.

| Metric | Formula |
|--------|---------|
| Daily change % | `(today_rate - prev_rate) / prev_rate * 100` |
| Weekly performance | `(last_rate - rate_7d_ago) / rate_7d_ago * 100` |
| Monthly performance | `(last_rate - rate_30d_ago) / rate_30d_ago * 100` |
| High / Low | `df['rate'].max()` / `.min()` over date range |
| 21-day rolling vol | `df['rate'].pct_change().rolling(21).std()` |
| Annualized vol | `rolling_std * sqrt(252)` |
| Spike detection | `abs(daily_pct) > 3 * df['rate'].pct_change().rolling(63).std()` |

Minimum data requirements: 2 rows for daily change, 21 rows for volatility. Return HTTP 422 if not enough data.

---

## Risk Alert Logic (`services/alert_engine.py`)

```python
def classify_risk(daily_change_pct: float, is_spike: bool) -> str:
    if is_spike:
        return "high"
    abs_change = abs(daily_change_pct)
    if abs_change < 0.5:
        return "low"
    elif abs_change < 1.0:
        return "medium"
    else:
        return "high"
```

Messages:
- **low**: "Normal movement. No action required."
- **medium**: "Moderate movement. Monitor closely."
- **high**: "Significant movement. Consider hedging or delaying FX transactions."
- **high (spike)**: "Unusual spike detected (>3σ). High volatility — review FX exposure immediately."

---

## AI Commentary Flow (`services/ai_service.py`)

1. Check `ai_commentary` table — if row exists for (base, quote, date), return cached.
2. Load: last 7 days of rates, today's daily_change_pct, risk_level.
3. Build prompt:
   ```
   You are a concise FX analyst. {BASE}/{QUOTE} moved {X}% on {DATE} (risk level: {LEVEL}).
   7-day rate history: {data}
   In 2-3 sentences, explain what happened and what this means for a business
   with {BASE}/{QUOTE} exposure (importer or exporter).
   ```
4. Call Groq: `model="llama3-70b-8192"`, `max_tokens=200`, `temperature=0.3`.
5. Insert into `ai_commentary`. Return commentary + `cached: false`.

**Error handling:** If Groq fails, return HTTP 502 — never block the main dashboard.

---

## Error Handling

| Scenario | Status | Detail |
|----------|--------|--------|
| Unknown currency code | 400 | "Unknown currency: {code}" |
| `from_date > to_date` | 400 | "Invalid date range" |
| Frankfurter + fallback both fail | 503 | "Exchange rate data unavailable" |
| Not enough data for volatility | 422 | "Need at least 21 days of data" |
| Groq API fails | 502 | "AI commentary unavailable" |

All errors use FastAPI `HTTPException` — consistent `{ detail: "..." }` JSON shape.

---

## Dependencies (`requirements.txt`)

```
fastapi>=0.111
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pydantic-settings>=2.0
httpx>=0.27
pandas>=2.0
numpy>=1.26
python-dotenv>=1.0
groq>=0.9
```

---

## Implementation Order

1. **Foundation** — `config.py`, `database.py`, `models.py`, `schemas.py`, `main.py`
2. **Seed script** — `scripts/seed_currencies.py` + currencies router
3. **Data ingestion** — `services/frankfurter.py` (with fallback) + rates router (historical endpoint first)
4. **Analytics** — `services/analytics.py` + remaining rates endpoints (daily-change, performance, high-low, volatility)
5. **Alerts** — `services/alert_engine.py` + alerts router
6. **Analysis** — `analysis.py` router + cross-pair summary logic
7. **AI** — `services/ai_service.py` + ai router
8. **Tests** — `tests/` covering analytics calculations and alert classification
9. **Documentation** — README with setup instructions and endpoint reference

---

## Verification

1. Run `uvicorn app.main:app --reload` — server starts, `/api/v1/currencies` returns currency list
2. Call `GET /api/v1/rates/USD/TND?from_date=2024-01-01&to_date=2024-12-31` — returns 250+ rows, SQLite populated
3. Repeat same call — instant response (no Frankfurter hit, served from cache)
4. Call `/api/v1/rates/EUR/USD/volatility?from_date=2023-01-01&to_date=2024-12-31` — returns rolling vol values
5. Call `GET /api/v1/alerts/USD/TND` — returns risk_level + message for latest date
6. Call `POST /api/v1/ai/commentary` with `{ base: "USD", quote: "TND", date: "2024-06-01" }` — returns Groq commentary
7. Call same POST again — returns same commentary with `cached: true`
8. Run `pytest tests/` — all analytics and alert logic tests pass
