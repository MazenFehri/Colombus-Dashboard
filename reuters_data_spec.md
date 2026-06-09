# Reuters / LSEG Data Integration — Requirements Specification

**Date:** 2026-06-09  
**Purpose:** Define exactly what data we need, where it comes from, what the API
responses look like, and how each piece maps to the current codebase.  
**Related:** `hedge_critic.md` (why we need this), `hedge_logic.md` (what we built)

---

## Table of Contents

1. [The LSEG / Reuters API landscape](#1-the-lseg--reuters-api-landscape)
2. [Data Category 1 — Money Market Rates (fixes CIP math)](#2-data-category-1--money-market-rates)
3. [Data Category 2 — Live Forward FX Rates (replaces CIP computation)](#3-data-category-2--live-forward-fx-rates)
4. [Data Category 3 — FX Implied Volatility (upgrades heuristic)](#4-data-category-3--fx-implied-volatility)
5. [Data Category 4 — Reuters News (grounds AI narrative)](#5-data-category-4--reuters-news)
6. [TND Specific Constraints](#6-tnd-specific-constraints)
7. [Access Model and Tiers](#7-access-model-and-tiers)
8. [Free / Open-Data Alternatives](#8-free--open-data-alternatives)
9. [Data Schema Definitions](#9-data-schema-definitions)
10. [Code Integration Map](#10-code-integration-map)
11. [Implementation Priority](#11-implementation-priority)

---

## 1. The LSEG / Reuters API Landscape

Reuters data is now sold under **LSEG (London Stock Exchange Group)** after the
Refinitiv acquisition. There are three separate products:

| Product | What it is | Best for |
|---------|-----------|----------|
| **LSEG Data Platform (RDP)** | REST/streaming API for pricing, rates, reference data | Forward rates, IR curves, IV |
| **Reuters News API** (`reutersconnect.com`) | Licensed news feed with tagging and full text | FX-tagged news, central bank articles |
| **Eikon/Workspace SDK** | Desktop/Python SDK on top of RDP | Quant research, not production APIs |

For a production web app, we target **RDP** (pricing data) + **Reuters News API** (news).

### Authentication — LSEG RDP

All RDP calls use OAuth2 Client Credentials:

```http
POST https://api.refinitiv.com/auth/oauth2/v1/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&scope=trapi
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 300,
  "scope": "trapi"
}
```

Token lifetime is 5 minutes — must be refreshed. All subsequent calls:
```http
Authorization: Bearer {access_token}
```

---

## 2. Data Category 1 — Money Market Rates

### Why we need this

The current `_INTEREST_RATES` dict uses **policy rates** (BCT key rate, Fed funds).
CIP requires **term money-market rates** — the interbank rate at the exact tenor
(1M, 3M, 6M) of the forward being priced. The gap:

| Currency | Policy rate (now) | 3M term rate | Error at 3M |
|----------|------------------|-------------|-------------|
| USD | 3.70% (Fed funds) | SOFR Term 3M ≈ 4.30–4.50% | ~70 bps underestimate |
| EUR | 2.10% (ECB deposit) | EURIBOR 3M ≈ 2.40–2.60% | ~40 bps underestimate |
| GBP | — | SONIA Term 3M ≈ 4.25% | completely absent |
| TND | 7.00% (BCT key) | TUNIBOR 3M ≈ 7.50–8.00% | ~50–100 bps underestimate |

### What to fetch — RDP Pricing endpoint

```http
GET https://api.refinitiv.com/data/pricing/v1/views/price?universe=USD3MFSR%3DX%2CEUR3MD%3D%2CGBP3MFSR%3DX
Authorization: Bearer {token}
```

**RIC codes (Reuters Instrument Codes):**

| Instrument | RIC | Description |
|-----------|-----|-------------|
| SOFR Term 1M | `USD1MFSR=X` | CME SOFR Term Rate — 1 month |
| SOFR Term 3M | `USD3MFSR=X` | CME SOFR Term Rate — 3 month |
| SOFR Term 6M | `USD6MFSR=X` | CME SOFR Term Rate — 6 month |
| EURIBOR 1M | `EUR1MD=` | Euro Interbank Offered Rate — 1M |
| EURIBOR 3M | `EUR3MD=` | Euro Interbank Offered Rate — 3M |
| EURIBOR 6M | `EUR6MD=` | Euro Interbank Offered Rate — 6M |
| SONIA Term 1M | `GBP1MFSR=X` | SONIA Compounded Index — 1M |
| SONIA Term 3M | `GBP3MFSR=X` | SONIA Compounded Index — 3M |
| SONIA Term 6M | `GBP6MFSR=X` | SONIA Compounded Index — 6M |
| TUNIBOR 3M | *Not on RDP* | BCT only — see §6 |

**RDP response shape:**

```json
{
  "universe": [
    {
      "ric": "USD3MFSR=X",
      "date": "2026-06-09",
      "fields": {
        "MID_PRICE": 4.3250,
        "BID":       4.3200,
        "ASK":       4.3300,
        "VALUE_DT":  "2026-06-09T14:30:00Z"
      }
    },
    {
      "ric": "EUR3MD=",
      "date": "2026-06-09",
      "fields": {
        "MID_PRICE": 2.4780,
        "BID":       2.4750,
        "ASK":       2.4810,
        "VALUE_DT":  "2026-06-09T10:00:00Z"
      }
    }
  ]
}
```

**Fields we extract:**

| Field | Use |
|-------|-----|
| `MID_PRICE` | The rate itself (e.g. `4.3250` = 4.325% annualised) |
| `VALUE_DT` | Timestamp — used for staleness check |

### Day-count conventions (needed to fix the CIP formula)

The current formula uses `t = months / 12` (exact fraction). Correct formula uses
the actual number of calendar days divided by the convention denominator:

| Currency | Convention | Denominator | Example 3M (91 days) |
|----------|-----------|-------------|----------------------|
| USD | ACT/360 | 360 | t = 91/360 = 0.25278 |
| EUR | ACT/360 | 360 | t = 91/360 = 0.25278 |
| GBP | ACT/365 | 365 | t = 91/365 = 0.24932 |
| TND | ACT/365 | 365 | t = 91/365 = 0.24932 |

The settlement date (spot date + tenor) is needed to count the actual days.
Standard FX spot settlement is T+2. So for a 3M forward struck today (2026-06-09):
- Spot date: 2026-06-11
- 3M forward settlement: 2026-09-11
- ACT/360: (91 + 0 holidays) / 360 = 0.25278

**Updated CIP formula:**

```python
from datetime import date, timedelta

DAY_COUNT = {"USD": 360, "EUR": 360, "GBP": 365, "TND": 365}

def cip_forward(spot: float, r_base: float, r_quote: float,
                base: str, quote: str, tenor_days: int) -> float:
    dc_base  = DAY_COUNT.get(base, 360)
    dc_quote = DAY_COUNT.get(quote, 360)
    t_base   = tenor_days / dc_base
    t_quote  = tenor_days / dc_quote
    return spot * (1 + r_quote * t_quote) / (1 + r_base * t_base)
```

**Tenor days (approximate — exact count requires a trading calendar):**

| Tenor | Approximate days |
|-------|----------------|
| 1M | 30–31 |
| 3M | 90–92 |
| 6M | 181–184 |

---

## 3. Data Category 2 — Live Forward FX Rates

### Why we need this

Instead of computing CIP ourselves (with all its approximations), we can pull
**actual interbank forward quotes** from Reuters. These already incorporate:
- Correct term rates
- Proper day count
- Bid/ask spread
- Market supply/demand on top of CIP

This completely replaces `compute_forward_rates()` for EUR/USD and GBP/USD.

> **Important caveat:** TND forward rates (NDFs) are illiquid and may not be
> available on RDP. See §6 for TND-specific handling.

### What to fetch — Outright forward rates

```http
GET https://api.refinitiv.com/data/pricing/v1/views/price?universe=EUR1M%3D%2CEUR3M%3D%2CEUR6M%3D%2CGBP1M%3D%2CGBP3M%3D%2CGBP6M%3D
Authorization: Bearer {token}
```

**RIC codes — outright forward rates:**

| Pair | Tenor | RIC | Notes |
|------|-------|-----|-------|
| EUR/USD | 1M | `EUR1M=` | Outright forward rate |
| EUR/USD | 3M | `EUR3M=` | Most liquid EUR/USD tenor |
| EUR/USD | 6M | `EUR6M=` | |
| GBP/USD | 1M | `GBP1M=` | |
| GBP/USD | 3M | `GBP3M=` | |
| GBP/USD | 6M | `GBP6M=` | |
| USD/TND | any | *NDF only, thin* | See §6 |
| EUR/TND | any | *NDF only, thin* | See §6 |

**Alternatively — FX swap points (forward points / pips):**

Banks quote forward rates as **swap points** (the difference from spot, in pips)
rather than outright rates. This is the more common market convention.

RIC codes for swap points:
- EUR/USD 3M swap points: `EUR3MFWD=`
- GBP/USD 3M swap points: `GBP3MFWD=`

```json
{
  "universe": [
    {
      "ric": "EUR3M=",
      "fields": {
        "BID":      1.1638,
        "ASK":      1.1644,
        "MID":      1.1641,
        "SPOT_BID": 1.1592,
        "SPOT_ASK": 1.1598,
        "FWD_POINTS_BID": 46.0,
        "FWD_POINTS_ASK": 46.0,
        "VALUE_DT": "2026-06-09T14:32:10Z",
        "TENOR":    "3M"
      }
    }
  ]
}
```

**Fields we extract:**

| Field | Use |
|-------|-----|
| `MID` | Midpoint forward rate (for display) |
| `BID` | Bank buys base currency at this rate |
| `ASK` | Bank sells base currency at this rate |
| `FWD_POINTS_BID/ASK` | Swap points in pips (useful for showing cost separately) |
| `SPOT_BID/ASK` | Spot rate at time of quote |
| `VALUE_DT` | Quote timestamp |

**Computed fields from API data:**

```python
# From API response
spot_mid = (bid["SPOT_BID"] + bid["SPOT_ASK"]) / 2
fwd_mid  = bid["MID"]
spread   = bid["ASK"] - bid["BID"]                          # bid-ask spread
pct_diff = (fwd_mid - spot_mid) / spot_mid * 100            # forward premium/discount
cost_of_hedging = (bid["ASK"] - bid["SPOT_MID"]) / bid["SPOT_MID"] * 100  # importer cost
```

---

## 4. Data Category 3 — FX Implied Volatility

### Why we need this

`calc_volatility()` returns **historical volatility** — how much the rate moved
in the past 21 days. **Implied volatility (IV)** is the market's forward-looking
estimate derived from option prices. It answers: *"how much does the market expect
this rate to move over the next N months?"*

Key difference: before an ECB or BCT meeting, IV spikes while historical vol is still calm.
IV is also what banks use internally to price forward contracts and assess hedging costs.

### What to fetch — ATM Implied Volatility surface

```http
GET https://api.refinitiv.com/data/pricing/v1/views/price?universe=EURUSD1MV%3DX%2CEURUSD3MV%3DX%2CGBPUSD1MV%3DX%2CGBPUSD3MV%3DX
Authorization: Bearer {token}
```

**RIC codes — ATM FX implied vol:**

| Pair | Tenor | RIC | Unit |
|------|-------|-----|------|
| EUR/USD | 1W | `EURUSD1WV=X` | % annualised |
| EUR/USD | 1M | `EURUSD1MV=X` | % annualised |
| EUR/USD | 3M | `EURUSD3MV=X` | % annualised |
| EUR/USD | 6M | `EURUSD6MV=X` | % annualised |
| GBP/USD | 1M | `GBPUSD1MV=X` | % annualised |
| GBP/USD | 3M | `GBPUSD3MV=X` | % annualised |
| USD/TND | — | *Not quoted* | See §6 |
| EUR/TND | — | *Not quoted* | See §6 |

**RDP response shape:**

```json
{
  "universe": [
    {
      "ric": "EURUSD3MV=X",
      "fields": {
        "MID_PRICE": 7.45,
        "BID":       7.40,
        "ASK":       7.50,
        "VALUE_DT":  "2026-06-09T14:00:00Z",
        "TENOR":     "3M"
      }
    }
  ]
}
```

`MID_PRICE = 7.45` means **7.45% annualised IV** — not 0.0745.

### How IV replaces the vol_elevated check

Current logic in `hedge_engine.py`:
```python
vol_elevated = annualized_vol >= _VOL_ELEVATED.get(quote, 0.07)
```

Improved logic with IV:
```python
# IV is forward-looking; historical vol is backward-looking.
# Use IV if available, fall back to historical vol.
effective_vol = implied_vol_3m if implied_vol_3m is not None else annualized_vol_historical
vol_elevated = effective_vol >= _VOL_ELEVATED.get(quote, 0.07)

# Also expose IV vs historical vol divergence as a signal:
vol_spike_expected = (
    implied_vol_3m is not None
    and annualized_vol_historical is not None
    and implied_vol_3m > annualized_vol_historical * 1.3  # IV 30% above hist vol
)
```

---

## 5. Data Category 4 — Reuters News

### Why we need this

The current news source is **Google News RSS** (`news.google.com/rss/search?q=...`).
Problems:
- Returns consumer-grade news, not financial news
- Almost never surfaces BCT (Banque Centrale de Tunisie) announcements
- No structured metadata (topic, currency, sentiment)
- Silent failures with no fallback signal

Reuters News provides:
- Professional financial journalism
- Structured taxonomy (FX, central banks, economic data)
- Currency-pair tagging at article level
- Headline + snippet + full text
- Timestamps with proper timezone

### Access — Reuters Connect API

**Base URL:** `https://api.reutersconnect.com/content/v1/`  
**Auth:** API key in `X-Api-Key` header (separate from RDP credentials)

```http
GET https://api.reutersconnect.com/content/v1/stories/search
X-Api-Key: YOUR_NEWS_API_KEY
Content-Type: application/json
```

### Endpoint: Story Search

```http
POST https://api.reutersconnect.com/content/v1/stories/search
X-Api-Key: YOUR_NEWS_API_KEY
Content-Type: application/json

{
  "query": {
    "bool": {
      "must": [
        { "term": { "subjects.code": "M:FRX" } }
      ],
      "should": [
        { "term": { "subjects.code": "M:TUN" } },
        { "term": { "currencies": "TND" } }
      ]
    }
  },
  "size": 5,
  "sort": [{ "versionCreated": "desc" }],
  "dateRange": {
    "start": "2026-06-08T00:00:00Z",
    "end":   "2026-06-09T23:59:59Z"
  }
}
```

### Reuters taxonomy codes we need

**Subject codes (topics):**

| Code | Meaning |
|------|---------|
| `M:FRX` | Foreign exchange markets |
| `M:CEN` | Central banks |
| `M:ECO` | Economic indicators |
| `M:INT` | Interest rates |
| `R:TUN` | Region: Tunisia |
| `R:EU` | Region: Eurozone |
| `R:US` | Region: United States |

**Currency codes (direct tags):**

| Code | Meaning |
|------|---------|
| `TND` | Tunisian Dinar |
| `EUR` | Euro |
| `USD` | US Dollar |
| `GBP` | British Pound |

**Building the query per pair:**

```python
PAIR_QUERY = {
    "EUR/USD": {
        "subjects": ["M:FRX", "M:CEN"],
        "currencies": ["EUR", "USD"],
        "regions": ["R:EU", "R:US"]
    },
    "GBP/USD": {
        "subjects": ["M:FRX", "M:CEN"],
        "currencies": ["GBP", "USD"],
        "regions": ["R:GB", "R:US"]
    },
    "USD/TND": {
        "subjects": ["M:FRX", "M:CEN", "R:TUN"],
        "currencies": ["TND", "USD"],
        "regions": ["R:TUN"]
    },
    "EUR/TND": {
        "subjects": ["M:FRX", "M:CEN", "R:TUN"],
        "currencies": ["TND", "EUR"],
        "regions": ["R:TUN", "R:EU"]
    },
}
```

### Reuters News API response shape

```json
{
  "totalCount": 42,
  "stories": [
    {
      "storyId": "RTRS-20260609-BCT001",
      "versionCreated": "2026-06-09T09:15:00Z",
      "firstCreated":   "2026-06-09T09:15:00Z",
      "headline": "Tunisia central bank holds key rate at 7.00 pct",
      "slug": "tunisia-central-bank-holds-key-rate",
      "description": "The Tunisian central bank (BCT) kept its key interest rate unchanged at 7.00 percent on Monday...",
      "bodyXhtml": "<p>TUNIS, June 9 (Reuters) - The Tunisian central bank...</p>",
      "subjects": [
        { "code": "M:CEN", "name": "Central Banks" },
        { "code": "M:FRX", "name": "Foreign Exchange" },
        { "code": "R:TUN", "name": "Tunisia" }
      ],
      "currencies": ["TND"],
      "urgency": 3,
      "source": {
        "name": "Reuters",
        "homeUrl": "https://www.reuters.com"
      },
      "canonical": "https://www.reuters.com/markets/currencies/..."
    }
  ]
}
```

**Fields we extract:**

| Field | Maps to in our code |
|-------|-------------------|
| `headline` | `NewsItem.headline` |
| `canonical` | `NewsItem.url` |
| `source.name` | `NewsItem.source` |
| `versionCreated` | `NewsItem.published_at` |
| `description` | Used in AI prompt (not stored, optional) |
| `subjects[].code` | Filter validation |

### How this replaces Google News RSS

Current `news.py` (`_fetch_and_store`):
```python
url = f"https://news.google.com/rss/search?q={tag}+currency&hl=en&gl=US&ceid=US:en"
feed = feedparser.parse(url)
```

Replacement:
```python
def _fetch_reuters_news(tag: str, on_date: date, limit: int = 5) -> list[dict]:
    query = _build_reuters_query(tag)
    resp = requests.post(
        "https://api.reutersconnect.com/content/v1/stories/search",
        headers={"X-Api-Key": settings.reuters_api_key},
        json={**query, "size": limit,
              "dateRange": {"start": f"{on_date}T00:00:00Z",
                            "end":   f"{on_date}T23:59:59Z"}},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json().get("stories", [])
```

---

## 6. TND Specific Constraints

TND is a **controlled/restricted currency** — the BCT fixes the exchange rate daily
against a basket. This creates specific limitations for every data category.

### 6.1 TND Forward Market Reality

| Instrument | Available on Reuters? | Notes |
|-----------|----------------------|-------|
| USD/TND spot | Yes — `USDTND=` | BCT-fixed daily |
| EUR/TND spot | Yes — `EURTND=` | Derived from USD/TND × EUR/USD |
| USD/TND forward | Very thin NDF | Not reliably quoted on RDP |
| EUR/TND forward | Very thin NDF | Not reliably quoted on RDP |
| TND IV | Not available | No active options market |

**Recommendation:** For TND pairs, keep the CIP-computed forward using TUNIBOR (when
available) rather than relying on Reuters forward quotes. The CIP estimate with a
proper TUNIBOR rate is actually more reliable than a thin NDF market quote.

### 6.2 TUNIBOR — The only TND term rate

TUNIBOR (Taux Interbancaire Tunisien) is the TND interbank rate, set by the BCT.
It is **not available on the Reuters RDP API**. Sources:

| Source | URL | Format | Frequency |
|--------|-----|--------|-----------|
| BCT Official | `https://www.bct.gov.tn/bct/siteprod/document.jsp?id=54` | HTML table | Daily |
| BCT Data Portal | `https://donnees.bct.gov.tn/` | CSV download | Daily |

**Typical TUNIBOR rates (as of 2026-06):**

| Tenor | Rate (approx) |
|-------|--------------|
| O/N | 6.80% |
| 1W | 6.90% |
| 1M | 7.10% |
| 3M | 7.30% |
| 6M | 7.50% |

These should replace the hardcoded `"TND": 0.07` with tenor-specific values.

**BCT scraper (replace or supplement current rate):**

```python
import requests
from bs4 import BeautifulSoup

BCT_TUNIBOR_URL = "https://donnees.bct.gov.tn/api/v1/series/TUNIBOR_3M"

def fetch_tunibor_3m() -> float | None:
    try:
        resp = requests.get(BCT_TUNIBOR_URL, timeout=10)
        data = resp.json()
        # BCT API returns latest observation
        return data["observations"][-1]["value"] / 100
    except Exception:
        return None  # fall back to hardcoded constant
```

### 6.3 BCT News — Reuters vs Direct

The BCT publishes official rate decisions and monetary policy reports.
Reuters covers some BCT decisions but not all. Supplement with:

| Source | URL | Notes |
|--------|-----|-------|
| BCT Press Releases | `https://www.bct.gov.tn/bct/siteprod/liste_communiques.jsp` | French/Arabic, HTML |
| Reuters Tunisia tag | Search `R:TUN + M:CEN` | English, best coverage |
| World Bank TUN | Global macro data | Quarterly, not real-time |

---

## 7. Access Model and Tiers

### LSEG Data Platform (RDP)

| Tier | Access | Monthly Cost (est.) |
|------|--------|---------------------|
| **Free / Developer** | developer.lseg.com — limited snapshots, no streaming | Free |
| **Individual** | Workspace API, personal use | ~$500/month |
| **Professional** | Full RDP, streaming, news | ~$2,000–5,000/month |
| **Enterprise** | Bulk, real-time, redistribution | Negotiated |

For a local treasury dashboard (non-redistributed, single user):
the **Developer tier** is sufficient for snapshots (refresh every 15 min).

### Reuters News API (Reuters Connect)

| Tier | Access | Monthly Cost (est.) |
|------|--------|---------------------|
| **Starter** | 10,000 requests/month, 48h delay | ~$200/month |
| **Standard** | 100,000 requests/month, real-time | ~$800/month |
| **Enterprise** | Unlimited, redistribution rights | Negotiated |

Contact: `newsapi@reuters.com` / `developer.lseg.com/en/api-catalog/refinitiv-news`

### Environment variables needed

```env
# LSEG RDP (pricing data — forward rates, IR curves, IV)
LSEG_CLIENT_ID=your_client_id
LSEG_CLIENT_SECRET=your_client_secret
LSEG_RDP_BASE=https://api.refinitiv.com

# Reuters News API (separate credential)
REUTERS_NEWS_API_KEY=your_news_key
REUTERS_NEWS_BASE=https://api.reutersconnect.com/content/v1

# BCT (no key needed — public scraping)
BCT_TUNIBOR_URL=https://donnees.bct.gov.tn/api/v1/series
```

---

## 8. Free / Open-Data Alternatives

If LSEG/Reuters access is not available, each data category has a free substitute:

### 8.1 Money Market Rates — Free

| Currency | Source | API | Free? |
|----------|--------|-----|-------|
| USD SOFR (all tenors) | St. Louis FRED | `https://api.stlouisfed.org/fred/series/observations?series_id=SOFR` | Yes (key req.) |
| EUR €STR overnight | ECB Data Portal | `https://data.ecb.europa.eu/api/v2/data/dataflow/ECB/EST/1.0/B.EU000A2X2A25.WT?lastNObservations=1` | Yes |
| EUR EURIBOR 3M | ECB Data Portal | `https://data.ecb.europa.eu/api/v2/data/dataflow/ECB/EURIBOR3MD_/1.0/...` | Yes |
| GBP SONIA | Bank of England | `https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?...` | Yes |
| TND TUNIBOR | BCT scrape | HTML table at bct.gov.tn | Yes (scraping) |

**FRED API example (SOFR Term 3M):**

```http
GET https://api.stlouisfed.org/fred/series/observations
  ?series_id=SOFR90DAYAVG
  &api_key=YOUR_FRED_KEY
  &sort_order=desc
  &limit=1
  &file_type=json
```

Response:
```json
{
  "observations": [
    {
      "date": "2026-06-06",
      "value": "4.3100"
    }
  ]
}
```

### 8.2 Implied Volatility — Free (limited)

| Source | Coverage | Notes |
|--------|----------|-------|
| CBOE FX Vol | EUR/USD, GBP/USD | Daily, 1-month only |
| `investing.com` scrape | Major pairs | Fragile |
| Option chain from CME | EUR/USD futures | Requires parsing |

Full IV surfaces (1W/1M/3M/6M per pair) require Reuters/Bloomberg or similar.

### 8.3 News — Free (what we already use)

| Source | Quality for TND | Quality for EUR/USD |
|--------|---------------|-------------------|
| Google News RSS | Poor | Moderate |
| Reuters RSS (public) | Moderate | Good |
| Reuters Open Newsroom | Good (limited) | Good |

Reuters has a public RSS feed that does NOT require a paid key:
```
https://feeds.reuters.com/reuters/financialsNews
https://feeds.reuters.com/reuters/technologyNews
```

These are category feeds, not pair-specific. Better than Google but not as good
as the full API with `subjects` filtering.

---

## 9. Data Schema Definitions

### 9.1 InterestRateRecord (replaces `_INTEREST_RATES` dict)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class InterestRateRecord:
    currency: str        # "USD", "EUR", "GBP", "TND"
    tenor: str           # "1M", "3M", "6M"
    rate: float          # annualised, decimal (0.043 = 4.30%)
    source: str          # "LSEG_RDP", "FRED", "ECB", "BCT", "HARDCODED"
    fetched_at: datetime
    day_count: int       # 360 or 365 — for CIP computation
```

**DB table: `interest_rates`**

```sql
CREATE TABLE interest_rates (
    id          INTEGER PRIMARY KEY,
    currency    TEXT NOT NULL,
    tenor       TEXT NOT NULL,           -- '1M', '3M', '6M'
    rate        REAL NOT NULL,           -- decimal, e.g. 0.043
    source      TEXT NOT NULL,
    fetched_at  DATETIME NOT NULL,
    day_count   INTEGER NOT NULL DEFAULT 360,
    UNIQUE(currency, tenor, DATE(fetched_at))
);
```

### 9.2 ForwardQuoteRecord (live forward from Reuters, replaces CIP computation)

```python
@dataclass
class ForwardQuoteRecord:
    base: str            # "EUR"
    quote: str           # "USD"
    tenor: str           # "3M"
    bid: float           # bank buys base at this rate
    ask: float           # bank sells base at this rate
    mid: float           # midpoint
    fwd_points_bid: float   # swap points (pips)
    fwd_points_ask: float
    spot_mid: float      # spot rate at time of quote
    source: str          # "LSEG_RDP" or "COMPUTED_CIP"
    quoted_at: datetime
```

**DB table: `forward_quotes`**

```sql
CREATE TABLE forward_quotes (
    id          INTEGER PRIMARY KEY,
    base        TEXT NOT NULL,
    quote       TEXT NOT NULL,
    tenor       TEXT NOT NULL,
    bid         REAL,
    ask         REAL,
    mid         REAL NOT NULL,
    spot_mid    REAL,
    pct_diff    REAL,            -- (mid - spot_mid) / spot_mid * 100
    source      TEXT NOT NULL,   -- 'LSEG_RDP' | 'COMPUTED_CIP'
    quoted_at   DATETIME NOT NULL,
    UNIQUE(base, quote, tenor, DATE(quoted_at))
);
```

### 9.3 ImpliedVolRecord

```python
@dataclass
class ImpliedVolRecord:
    base: str
    quote: str
    tenor: str           # "1M", "3M", "6M"
    atm_vol: float       # annualised, decimal (0.0745 = 7.45%)
    source: str
    quoted_at: datetime
```

**DB table: `implied_vols`**

```sql
CREATE TABLE implied_vols (
    id          INTEGER PRIMARY KEY,
    base        TEXT NOT NULL,
    quote       TEXT NOT NULL,
    tenor       TEXT NOT NULL,
    atm_vol     REAL NOT NULL,   -- decimal, e.g. 0.0745
    source      TEXT NOT NULL,
    quoted_at   DATETIME NOT NULL,
    UNIQUE(base, quote, tenor, DATE(quoted_at))
);
```

---

## 10. Code Integration Map

How each data category maps to the current codebase:

| Data | Current code | After integration |
|------|-------------|-------------------|
| Money market rates | `hedge_engine._INTEREST_RATES` (dict constant) | `services/ir_service.py` fetches from FRED/ECB/RDP; stored in `interest_rates` table |
| Forward rates | `hedge_engine.compute_forward_rates()` (CIP with policy rates) | `services/forward_service.py` — try RDP first, fall back to CIP with term rates |
| Implied vol | `analytics.calc_volatility()` (historical vol only) | `services/iv_service.py` — fetches from RDP; exposed in `build_snapshot()` as `implied_vol` |
| News | `news.py` — Google RSS + feedparser | `news.py` — Reuters Connect API first, Google RSS fallback |
| Hedge heuristic | `hedge_engine.compute_signal()` — uses hardcoded vol threshold | Uses `vol_regime` from snapshot + IV if available |
| AI prompt | `hedge_service.py` — no news context | Injects top 3 Reuters headlines into prompt alongside forward rates |

### New service files needed

```
Backend/app/services/
├── ir_service.py       # fetch + cache interest rates (FRED, ECB, BCT, fallback to constants)
├── forward_service.py  # fetch + cache live forward quotes (RDP), fallback to CIP
├── iv_service.py       # fetch + cache implied vol (RDP), fallback to None
└── lseg_client.py      # shared OAuth2 token management for all RDP calls
```

---

## 11. Implementation Priority

### Phase 1 — No paid API needed (1–2 days)

1. **Fix vol_elevated check** — use `vol_regime` from `build_snapshot` instead of hardcoded thresholds in `hedge_engine.py`. Zero new dependencies.

2. **Inject news into hedge prompt** — reuse `get_headlines()` from `news.py` and pass the same headlines into `hedge_service`'s Groq prompt. Zero new code needed.

3. **Add settlement date input** — add `settlement_date` query param to the hedge endpoint; compute `tenor_days` from it; use the matching forward row.

4. **Replace policy rates with free term rates** — build `ir_service.py` pulling SOFR from FRED (free) and EURIBOR from ECB portal (free); store in `interest_rates` table; TND stays hardcoded until TUNIBOR scraped.

5. **Fix day-count convention** — update `compute_forward_rates()` to use `ACT/360` for USD/EUR and `ACT/365` for GBP/TND.

### Phase 2 — FRED + ECB + BCT (free, 2–3 days)

6. **BCT TUNIBOR scraper** — replace hardcoded `7.00%` with live 3M TUNIBOR from BCT data portal.

7. **FRED SOFR scraper** — pulls daily SOFR Term 3M and 6M, updates `interest_rates` table.

8. **ECB EURIBOR scraper** — pulls 3M/6M EURIBOR from ECB Data Portal.

9. **Public Reuters RSS** — upgrade news fetcher to try Reuters category RSS before Google; same `feedparser` code, different URL.

### Phase 3 — LSEG RDP (paid, 1 week)

10. **`lseg_client.py`** — OAuth2 token manager with auto-refresh (5-min TTL).

11. **`forward_service.py`** — fetches `EUR3M=`, `GBP3M=`, etc. from RDP; stores in `forward_quotes` table; falls back to CIP for TND.

12. **`iv_service.py`** — fetches ATM IV from RDP; used in vol_elevated check.

13. **Full Reuters News API** — replaces Google RSS with `subjects`-filtered Reuters stories; significantly improves TND/BCT coverage.
