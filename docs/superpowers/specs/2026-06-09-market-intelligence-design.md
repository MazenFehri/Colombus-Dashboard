# Market Intelligence — News + Deeper Analytics — Design Spec

**Date:** 2026-06-09
**Status:** Approved (design), pending spec review
**Branch:** `market-intelligence`

## Goal

Make the dashboard's market intelligence genuinely intelligent by enriching the
AI commentary with (a) **real news headlines** explaining *why* a rate moved and
(b) **deeper computed signals** (trend, volatility regime, momentum). The signals
also surface in the UI and are time-travel aware via the existing snapshot
endpoint. News and the assembled AI context are **live-only** (today).

## Context

- Data is now 100% Frankfurter v2 (BCT scraper and CSV removed). Any prior
  roadmap references to "BCT scrape failures", BCT single-date retries, or
  TND-specific BCT scraping are obsolete.
- The app runs as a **local demo / portfolio** project — not 24/7. So an
  always-on background scheduler and a `FetchLog` audit table are **out of
  scope**; request-time fetch-and-cache with graceful degradation is the pattern.
- Today's live AI prompt (`ai_service.get_or_generate_commentary`) passes only
  `change_pct`, `risk_level`, and a 7-day history — and calls `classify_risk`
  **without** the `quote` arg, so its risk label is *not* TND-calibrated. This
  spec fixes that.

## Decisions (from brainstorming)

1. Build features **1 (news) + 3 (deeper analytics) together** — they feed one
   enriched `MarketContext`.
2. **Keyless RSS** for news (Google News RSS + `feedparser`); no API key, no rate
   limits. Must degrade to `[]` on any failure so a demo never breaks.
3. Analytics signals (trend, vol_regime, momentum) go into the existing
   `build_snapshot` / `SnapshotOut` → **time-travel aware**, surfaced in the UI.
4. News + `MarketContext` are **live-only** (RSS can't reliably fetch historical
   headlines; the AI card already does not time-travel).
5. **Out of scope (YAGNI for demo):** APScheduler, `FetchLog`, cross-pair
   correlation endpoint, alert-density endpoint.

---

## Architecture & data flow

```
LIVE AI COMMENTARY (today only)              TIME-TRAVELABLE DASHBOARD
POST /ai/commentary                          GET /analysis/{b}/{q}/snapshot?as_of=
        |                                            |
 get_or_generate_commentary                   build_snapshot(df, as_of, quote)
        |                                            |  + NEW signals:
 build_market_context(db, b, q, date)                |    trend, vol_regime, momentum
   |- analytics: daily_change, spike,                |
   |   trend, vol_regime, momentum  <---- shared --->|  (returned in SnapshotOut ->
   |- alert_engine.classify_risk(quote)              |   UI trend arrow + regime badge)
   |- news.get_headlines(db, tag, today)
        |
   build_prompt(ctx)  ->  Groq LLM  ->  cache (AiCommentary)
```

---

## Backend

### 1. News service — `app/services/news.py`

- **Source:** Google News RSS (keyless), parsed with `feedparser`.
  URL: `https://news.google.com/rss/search?q=<url-encoded query>&hl=en-US&gl=US&ceid=US:en`.
- **Pair → tag → query:**
  | Pair | tag | query |
  |------|-----|-------|
  | EUR/USD | `EURUSD` | `EUR USD exchange rate` |
  | GBP/USD | `GBPUSD` | `GBP USD pound dollar exchange rate` |
  | USD/TND, EUR/TND | `TND` | `Tunisian dinar OR BCT OR Tunisia economy` |
  A `pair_to_tag(base, quote) -> str` helper centralises this (TND quote wins).
- **`get_headlines(db, tag, on_date, limit=3) -> list[NewsItem]`**
  1. If `NewsItem` rows exist for `(pair_tag=tag, fetched_date=on_date)`, return up
     to `limit` of them (ordered by `published_at` desc).
  2. Else fetch the feed, take entries from the **last 48h**, keep up to `limit`,
     store each as a `NewsItem`, return them.
  3. **Any exception (network, parse, empty) → return `[]`.** Commentary proceeds
     without news. Failures must never propagate.
- Caching is per `(pair_tag, fetched_date)`; a `UniqueConstraint(pair_tag, url,
  fetched_date)` prevents duplicate rows on concurrent fetches.

### 2. `NewsItem` model — `app/models.py`

```
NewsItem
  id            integer PK
  pair_tag      text     not null     # "EURUSD" | "GBPUSD" | "TND"
  headline      text     not null
  source        text     not null
  url           text     not null
  published_at  datetime nullable
  fetched_date  date     not null     # dashboard date this was pulled for
  created_at    datetime server_default=now
  UniqueConstraint(pair_tag, url, fetched_date)
```

### 3. Analytics signals — `app/services/analytics.py`

All date-aware (operate on the already-sliced df), reuse `_normalized_returns`,
and return `None` when history is insufficient (never raise into the snapshot).

- **`calc_trend(df) -> dict | None`** — needs ≥30 rows.
  `ma7 = mean(last 7 rates)`, `ma30 = mean(last 30 rates)`.
  `direction = "neutral" if abs(ma7-ma30)/ma30 < 0.001 else ("bullish" if ma7>ma30 else "bearish")`.
  Returns `{ "direction": str, "ma7": float, "ma30": float }`.
- **`calc_vol_regime(df) -> str | None`** — needs ≥ ~111 rows (21d vol + 90 obs of it).
  Compute the 21-day rolling normalized-return std series; `current = last value`,
  `avg = mean of the last 90 values of that series`.
  `"elevated" if current > 1.5*avg`, `"compressed" if current < 0.6*avg`, else `"normal"`.
  Returns `None` if the rolling series has < 90 usable points or `avg == 0`.
- **`calc_momentum(df) -> float | None`** — needs ≥3 rows.
  `today = pct_change[-1]`, `yest = pct_change[-2]` (normalized returns, as %).
  `None` if `abs(yest) < 1e-9`, else `round((today - yest)/abs(yest), 4)`.

### 4. `build_snapshot` extension — `app/services/analytics.py`

Add `trend` (direction string or `None`), `vol_regime` (string or `None`),
`momentum` (float or `None`) to the returned dict, computed from the same
`sliced` df already used for the other metrics. No behaviour change to existing
fields.

### 5. `SnapshotOut` schema — `app/schemas.py`

Add:
```
trend:      str | None     # bullish | bearish | neutral
vol_regime: str | None     # elevated | normal | compressed
momentum:   float | None
```

### 6. MarketContext + prompt — `app/services/ai_service.py`

```python
@dataclass
class MarketContext:
    pair: str
    date: date
    change_pct: float
    risk_level: str
    spike: bool
    rate_history: list[str]      # last 7 "YYYY-MM-DD: rate"
    trend_direction: str | None
    vol_regime: str | None
    momentum: float | None
    headlines: list[NewsItem]    # may be empty
```

- **`build_market_context(db, base, quote, target_date) -> MarketContext`** —
  assembles the struct from `analytics` + `news.get_headlines` +
  `alert_engine.classify_risk(change_pct, spike=spike, quote=quote)`  ← **the
  quote-aware fix.** Pure assembly; the only I/O is the (already-cached) news
  fetch.
- **`build_prompt(ctx) -> str`** — renders the enriched prompt. When
  `ctx.headlines` is empty, the "Recent headlines" block is omitted (no empty
  bullet list). Trend/regime/momentum lines are omitted when `None`.
- **`get_or_generate_commentary`** uses these two functions; Groq call and
  `AiCommentary` caching unchanged. **Returns `(commentary, is_cached, headlines)`**
  so the API can surface the sources used. (Cached path returns stored commentary
  with `headlines = []` — historical headlines aren't persisted against the
  commentary; acceptable.)

### 7. Commentary endpoint — `app/routers/ai.py` + schema

Extend the commentary response to include the headlines used:
```
CommentaryOut:
  commentary: str
  date:       date
  cached:     bool
  headlines:  list[ { headline: str, source: str, url: str } ]   # NEW, may be []
```

---

## Frontend

### Data layer
- `client.ts` `Snapshot` + `PairAnalysis`: add `trend`, `volRegime`, `momentum`
  (all nullable). Map from the snapshot response.
- `fetchCommentary` returns `{ commentary, headlines }` (headlines may be empty).
- `endpoints.ts`: unchanged (snapshot + commentary URLs already exist).

### UI
- **Trend arrow + volatility-regime badge** near the KPI / risk area, driven by
  `usePairAnalysis(pair, asOf)` so they follow the selected date:
  - trend: ▲ bullish (green) / ▼ bearish (red) / → neutral (muted); hidden when `null`.
  - regime: small pill "Elevated" (amber) / "Normal" (muted) / "Compressed" (blue);
    hidden when `null`.
- **MarketIntelligence card:** under the AI commentary, render a "Sources" list of
  the returned `headlines` (title links to `url`, with `source`). Hidden when empty.
  Card stays **live** (no `asOf`).

---

## Error handling / degradation

| Failure | Behaviour |
|---------|-----------|
| News fetch/parse error or empty feed | `get_headlines` returns `[]`; commentary generated without a headlines block; UI shows no Sources list. |
| Missing Groq key | Unchanged from today (commentary generation errors as it does now). |
| Insufficient history for a signal | Field is `null`; UI hides that arrow/badge. |
| Time-travel (`as_of` set) | Snapshot signals computed as-of that date; **no news** (AI card is live-only). |

---

## Testing

**Backend**
- `news.py`: with `feedparser.parse` monkeypatched — parses entries, filters to
  last 48h, caps at `limit`, caches to `NewsItem`, dedups on re-call; on a raised
  exception returns `[]`.
- `analytics`: `calc_trend` (bullish/bearish/neutral + `None` under 30 rows),
  `calc_vol_regime` (elevated/normal/compressed + `None` when too short),
  `calc_momentum` (sign + `None` when yesterday≈0 / too short).
- `build_snapshot`: new fields present and `None` near the data-start edge.
- `build_market_context`: assembles fields; risk uses the TND threshold for a
  `/TND` pair; `build_prompt` includes the headline block only when headlines
  exist and omits `None` signal lines.
- Snapshot endpoint returns the three new fields; commentary endpoint returns
  `headlines`.

**Frontend**
- `tsc --noEmit` clean. `fetchPairAnalysis` maps the new fields; the badge/arrow
  render for each direction/regime and disappear when `null`.

---

## Out of scope

- APScheduler / proactive refresh, `FetchLog`, `fetched_at` column.
- Cross-pair correlation and alert-density endpoints.
- Historical (time-traveled) news; AI commentary for past dates.
- Spot-vs-forward recommendation (separate `forward_spot.md`).
