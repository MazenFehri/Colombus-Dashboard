# Research & Optimization Roadmap

> Research document covering three optimization vectors: complete data persistence, news-augmented market intelligence, and deeper analytics from the data we already hold.

---

## Status & Decisions — 2026-06-09

Two facts have changed since this doc was first written, and a direction has been chosen:

1. **Data is now 100% Frankfurter v2.** The BCT scraper and the CSV were removed.
   Every premise below that assumes BCT scraping (silent BCT gaps, BCT single-date
   retry holes, TND-specific BCT/TAP scraping) is **obsolete** — Frankfurter returns
   continuous, aligned history for all four pairs including TND.
2. **The app runs as a local demo / portfolio**, not 24/7. So the always-on
   **APScheduler** + **FetchLog** machinery (originally priority #1–2) is **deprioritized**
   — it can't run reliably when the app isn't up. The right pattern is request-time
   **fetch-and-cache with graceful degradation**.

**Chosen next build (see `docs/superpowers/specs/2026-06-09-market-intelligence-design.md`):**
combine **news-augmented intelligence (§2)** and **deeper analytics (§3)** into one
enriched `MarketContext` that drives the AI commentary, with the analytics signals
also surfaced in the UI via the existing snapshot endpoint.

- **News source:** keyless **Google News RSS** + `feedparser` (no API key / rate
  limit; degrades to `[]` on any failure). This supersedes the GNews-API
  recommendation in §2a below.
- **Signals built first:** trend (MA7/MA30), volatility regime, momentum — folded
  into `build_snapshot` so they are **time-travel aware**.
- **Risk fix:** the live AI prompt currently calls `classify_risk` *without* `quote`,
  so its label is not TND-calibrated; `build_market_context` fixes this.
- A deterministic **composite risk index** (shock + vol regime + abnormality,
  fixed weights — distilled from the experimental `risk.py`, dropping its broken
  PCA) is a strong follow-on but is **not** in the current build.

---

## 1. Complete Data Persistence

### Current State

Data is fetched **lazily** — only when a user hits an endpoint. The `_ensure_rates_cached` check re-fetches only if fewer than 80 % of expected business days are present. This means:

- A gap in BCT data (public holiday, scrape failure) is silently accepted and never retried.
- The first user of the day may wait while rates are fetched before their dashboard loads.
- There is no record of when data was last successfully fetched or whether it is stale.
- The `ExchangeRate` table has no `fetched_at` or `updated_at` column, so there is no way to know data freshness from the DB alone.

### What Is Missing

| Gap | Impact |
|-----|--------|
| No proactive daily refresh | Dashboard can serve yesterday's data as "today" |
| No fetch audit log | Silent failures; gaps accumulate invisibly |
| No staleness indicator on `ExchangeRate` rows | Frontend cannot warn the user that data may be old |
| BCT single-date failures never retried | Public holidays leave permanent holes |

### Proposed Solution

#### a. Background Scheduler (APScheduler)

Add a lightweight in-process scheduler that runs two jobs:

| Job | Schedule | What it does |
|-----|----------|--------------|
| `refresh_all_pairs` | Daily at 17:30 UTC (after Frankfurt close) | Fetch all 4 pairs for today; upsert into `exchange_rates` |
| `backfill_gaps` | Daily at 18:00 UTC | Scan the last 90 days for missing business days per pair; re-fetch them |

This turns data from *reactive* to *proactive* — the dashboard is always ready before the first user request.

#### b. `FetchLog` Table

```
FetchLog
  id            integer PK
  base_currency text
  quote_currency text
  from_date     date
  to_date       date
  source        text        ("frankfurter" | "bct" | "fawazahmed")
  rows_fetched  integer
  success       boolean
  error_msg     text nullable
  fetched_at    datetime    (server_default=now)
```

Every fetch attempt (success or failure) writes a row. This makes gaps observable and gives an audit trail for debugging BCT scrape issues.

#### c. `fetched_at` on `ExchangeRate`

Add a `fetched_at` datetime column (server default: `now()`). The frontend can compare this against today's date to display a freshness badge: **"Updated today"** vs **"Last updated 2 days ago"**.

#### d. Manual Refresh Endpoint

`POST /api/v1/admin/refresh?pair=USD/TND` — triggers an immediate re-fetch for a specific pair and date range. Useful for operators when  data is known to have been missing.

---

## 2. News-Augmented Market Intelligence

### Current State

The AI commentary prompt contains:
- `change_pct` — the daily percentage move
- `risk_level` — LOW / MEDIUM / HIGH
- 7-day rate history as a text list

It does **not** contain any information about *why* the rate moved. The AI can describe the *what* but is forced to speculate about the *why*, which reduces accuracy and usefulness.

### What Is Missing

Context the AI needs to produce accurate interpretations:
- Central bank decisions ( rate changes, Fed/ECB meetings)
- Macroeconomic releases (CPI, GDP, trade balance)
- Geopolitical events (election results, sanctions, trade deals)
- Commodity prices (oil, phosphates for TND-specific context)

### Proposed Solution

#### a. News Fetcher Service (`services/news.py`)

Fetch and cache headlines per pair per day.

**Chosen source (2026-06-09): keyless Google News RSS** + `feedparser` — no API key,
no rate limit, query-able, ideal for a local demo.
- Query template: `"EUR USD exchange rate"` for EUR/USD
- Query template: `"Tunisian dinar OR BCT OR Tunisia economy"` for TND pairs
- URL: `https://news.google.com/rss/search?q=<query>&hl=en-US&gl=US&ceid=US:en`

> _Originally this section recommended the GNews API (100 req/day). That was
> superseded by keyless RSS to remove the API-key dependency and rate-limit risk
> in a demo. GNews-with-RSS-fallback remains a valid upgrade if richer, query-
> targeted results are ever needed._

**Fetch strategy:**
- Fetch once per pair per day (cached in `NewsItem` table)
- Pull top 3–5 headlines from the last 48 hours
- Store title + source + URL + published_at

#### b. `NewsItem` Table

```
NewsItem
  id            integer PK
  pair_tag      text        ("EUR/USD", "TND")
  headline      text
  source        text
  url           text
  published_at  datetime
  fetched_date  date        (the dashboard date this was pulled for)
```

`pair_tag` can be a currency code rather than a full pair — "TND" covers both USD/TND and EUR/TND headlines.

#### c. Enriched AI Prompt

The updated prompt structure:

```
You are a concise FX analyst.

Pair: {base}/{quote}
Date: {date}
Daily move: {change_pct:+.2f}%
Risk level: {risk_level}
7-day rate history: {history}
Trend (7d vs 30d MA): {trend_direction}   ← new
Alert count last 30 days: {high_count} HIGH, {medium_count} MEDIUM   ← new
Recent headlines:
  - {headline_1} ({source_1})
  - {headline_2} ({source_2})
  - {headline_3} ({source_3})   ← new

In 3–4 sentences, explain what drove this movement, what context the headlines provide,
and what this means for a business with {base}/{quote} exposure.
```

This gives the AI the *cause* (headlines), the *pattern* (trend and alert history), and the *magnitude* (daily change + risk), enabling genuinely accurate interpretations rather than generic statements.

#### d. TND-Specific News Sources

TND pairs benefit from domain-specific sources that generic APIs may miss:

| Source | Type | Coverage |
|--------|------|----------|
| BCT press releases (`bct.gov.tn`) | Scrape | Official rate decisions, monetary policy |
| TAP news agency (`tap.info.tn`) | RSS | Tunisian economic events |
| Tunis Afrique Presse | RSS | Government economic announcements |

These can supplement the general news feed when the pair tag is TND.

---

## 3. Intelligence Extraction from Existing Data

### What We Already Have

| Table | Depth | Potential |
|-------|-------|-----------|
| `exchange_rates` | Full rate history per pair | Trend, momentum, correlation, regime detection |
| `alerts` | Daily risk classification per pair | Alert density, risk calendar, pattern analysis |
| `ai_commentary` | Cached AI text per pair per day | Sentiment analysis (future) |

### Proposed Analytics

#### a. Trend Signal

**7-day MA vs 30-day MA crossover** — a simple but widely used directional indicator.

```
trend = "bullish"  if MA7 > MA30
trend = "bearish"  if MA7 < MA30
trend = "neutral"  if |MA7 - MA30| / MA30 < 0.001
```

Exposed as: `GET /api/v1/rates/{base}/{quote}/trend`
Response: `{ direction: "bullish" | "bearish" | "neutral", ma7: float, ma30: float }`

Used in: AI prompt (trend direction), frontend KPI cards (small directional arrow).

#### b. Alert Density

Count of HIGH and MEDIUM alerts over the last 30 days per pair.

```
GET /api/v1/alerts/{base}/{quote}/density
Response: { high_count: int, medium_count: int, period_days: 30 }
```

High density (e.g. 8 HIGH alerts in 30 days) indicates a structurally volatile period — useful context for the AI and for a new **risk calendar heatmap** component in the frontend.

#### c. Cross-Pair Correlation

EUR/USD and EUR/TND share the EUR base; USD/TND and EUR/TND share the TND quote. Their daily returns should be correlated. A divergence (one rising while the other falls) is an early warning of idiosyncratic TND movement.

```
GET /api/v1/analysis/correlation
Response: {
  "EUR/USD × EUR/TND": 0.72,
  "USD/TND × EUR/TND": 0.88
}
```

Computed as Pearson correlation of daily `pct_change` over the last 60 days.

#### d. Volatility Regime

Compare current 21-day rolling volatility against the 90-day rolling average of that vol. If current vol is significantly above its own average, the pair is in a **high-vol regime**.

```
vol_regime = "elevated"  if current_vol > 90d_avg_vol * 1.5
vol_regime = "compressed" if current_vol < 90d_avg_vol * 0.6
vol_regime = "normal"   otherwise
```

Exposed alongside the existing `/volatility` endpoint as an additional `regime` field.

#### e. Momentum Score

Rate of change of the rate of change — captures acceleration.

```
momentum = (change_pct_today - change_pct_yesterday) / |change_pct_yesterday|
```

Positive momentum: the move is accelerating. Negative: it is reversing. Used to give the AI a sense of whether this is a one-day event or a developing trend.

#### f. Richer AI Context Object

Consolidate all of the above into a single `MarketContext` struct built before the AI call:

```python
@dataclass
class MarketContext:
    pair: str
    date: date
    change_pct: float
    risk_level: str
    spike: bool
    rate_history: list[str]       # last 7 days
    trend_direction: str          # bullish / bearish / neutral
    high_alerts_30d: int
    medium_alerts_30d: int
    vol_regime: str               # elevated / normal / compressed
    momentum_score: float
    headlines: list[str]          # top 3 news headlines
```

The AI prompt is built from this struct. This separates *data assembly* from *prompt construction*, making the system easier to extend.

---

## Priority Order

Re-prioritized 2026-06-09 for the local-demo context (scheduler/FetchLog dropped to the bottom):

| Priority | Feature | Effort | Value | Status |
|----------|---------|--------|-------|--------|
| 1 | News (keyless RSS) + `NewsItem` + enriched prompt | Medium | High — biggest AI quality jump | **Building now** |
| 2 | Trend + volatility regime + momentum signals (in snapshot) | Low | Medium — feeds AI + UI | **Building now** |
| 3 | `MarketContext` consolidation + quote-aware risk fix | Low | High — clean, testable, fixes TND label | **Building now** |
| 4 | Composite risk index (shock + regime + abnormality) | Low | Medium — analytical depth, deterministic | Strong follow-on |
| 5 | Cross-pair correlation endpoint | Low | Medium — novel insight | Deferred |
| 6 | Risk calendar heatmap (frontend) | Medium | Medium — visual impact | Deferred |
| 7 | Background scheduler + `FetchLog` + `fetched_at` | Medium | Low for local demo (app isn't 24/7) | Deferred (not-for-demo) |

---

## Architecture Overview

```
Scheduler (APScheduler)
    └── refresh_all_pairs  → ExchangeRate (upsert) + FetchLog
    └── backfill_gaps      → ExchangeRate (fill holes) + FetchLog
    └── fetch_news_daily   → NewsItem (upsert per pair per day)

API Layer
    └── /rates/../trend        → analytics.calc_trend()
    └── /alerts/../density     → analytics.calc_alert_density()
    └── /analysis/correlation  → analytics.calc_correlation()
    └── /rates/../volatility   → + regime field

AI Commentary
    └── build_market_context()  → MarketContext
    └── build_prompt(ctx)       → prompt string
    └── Groq(llama-3.3-70b)    → commentary text
    └── AiCommentary (cache)
```

All new analytics are computed from the existing `exchange_rates` and `alerts` tables — no new external data required beyond the news feed. The news feed adds one external dependency (GNews or RSS) with a clear fallback path (serve commentary without headlines if fetch fails).
