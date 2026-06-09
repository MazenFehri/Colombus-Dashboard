# News Section — Design Spec

**Date:** 2026-06-07
**Feature:** Date-aware FX news section + news-aware AI explainer
**Status:** Approved design, pending implementation plan

---

## 1. Goal

Add a **News** section to the Colombus FX dashboard that shows, for the currently
selected pair and date, the headlines that relate to that pair's movement. The
existing **Market Intelligence** (AI explainer) stays its own section but becomes
**news-aware** — it can cite real events in its commentary.

The two sections are deliberately decoupled:

- **Market Intelligence** — AI commentary about the rate move, now able to reference the day's headlines.
- **News** (new, separate section below it) — the actual articles, in two layers:
  - **Why it moved** — top 2–3 most relevant headlines for the pair/date.
  - **More news** — a broader list for context.

## 2. Scope decisions

| Decision | Choice |
|---|---|
| Time scope | News matches the dashboard's shown date. If that date is "today/latest", use the recent window. |
| Source (v1) | **GDELT DOC 2.0 API** — free, no API key, no daily limit, global coverage incl. Tunisia. Reliable for the **most recent ~3 months**. |
| Older dates (v2) | **Alpha Vantage NEWS_SENTIMENT** fallback for dates beyond GDELT's window. Increment 2, behind the same provider interface. |
| AI role | One Groq call. The existing explainer receives the top-3 headlines and may cite them. No separate curation LLM call in v1. |
| Curation (v1) | "Why it moved" = top 3 by GDELT's own relevance/recency ranking. AI reranking is a later enhancement. |
| TND languages | TND pairs query **English + French** (most Tunisian economic coverage is French). |

**Accepted limitation:** GDELT reliably serves only ~3 months of news. Older
dates degrade to an empty state until the Alpha Vantage fallback (v2) lands — and
even then, older **USD/TND / EUR/TND** dates may stay empty because Alpha Vantage
is US-market-centric. The v2 fallback mainly rescues EUR/USD and GBP/USD history.

## 3. Architecture

```
Frontend (App.tsx)
  ├─ MarketIntelligence (existing, AI) — now news-aware, cites headlines
  └─ News (NEW separate section)
       • "Why it moved" : top-3 (is_top) items
       • "More news"    : remaining headline list
              │ GET /api/v1/news/{base}/{quote}?date=YYYY-MM-DD
              ▼
Backend
  routers/news.py  ──►  services/news_service.py
                          get_or_fetch_news(db, base, quote, date)
                            1. cache hit (fresh)? → return
                            2. miss → provider chain .fetch(base, quote, date)
                            3. store articles, return
                          services/news_providers/
                            gdelt.py          (DOC 2.0, keyword+country+lang, no key)   [v1]
                            alphavantage.py   (NEWS_SENTIMENT, key, fallback)           [v2]

  ai_service.get_or_generate_commentary(..., headlines=None)
     ← gains optional `headlines` arg so the explainer can reference the news.
       One Groq call, news-aware. Still cached per pair/date in ai_commentary.
```

### Provider interface

```python
class NewsProvider(Protocol):
    def fetch(self, base: str, quote: str, on_date: date) -> list[Article]: ...
```

A `news_service` resolves providers as an ordered **fallback chain**
(`[gdelt]` in v1; `[gdelt, alphavantage]` in v2). The first provider that returns
articles wins. This keeps source selection out of the router and lets v2 drop in
without touching callers.

### Pair → query mapping

| Pair | Keywords | Countries (FIPS) | Languages |
|---|---|---|---|
| EUR/USD | "euro dollar", "ECB", "Federal Reserve", "eurozone economy" | US, EU | English |
| GBP/USD | "pound dollar", "sterling", "Bank of England" | US, UK | English |
| USD/TND | "Tunisian dinar", "Tunisia economy", "Banque Centrale de Tunisie" | TN, US | English, French |
| EUR/TND | "Tunisian dinar euro", "Tunisia trade", "BCT" | TN, EU | English, French |

The mapping lives in one config/dict in `gdelt.py` (or a shared `news_config.py`),
so adding/tuning queries is a single-file change.

## 4. Data model — new `news_articles` table

```
news_articles
  id              (pk)
  base_currency   \
  quote_currency   } cache key: pair + day
  date            /
  title
  url             (dedupe per pair/date)
  source          (domain, e.g. reuters.com)
  published_at
  language
  relevance       (float, nullable — provider score)
  is_top          (bool — true = "why it moved" item)
  fetched_at      (for today's-news refresh TTL)
```

One fetch per pair per day populates rows; later loads serve from SQLite,
mirroring how `ai_commentary` caches per pair+date.

## 5. Caching / refresh

- **Historical dates:** cache permanently (a past day's news doesn't change).
- **Today's date:** cache, but **refetch if `fetched_at` is older than ~6h** so
  intraday news stays fresh without hammering GDELT.

## 6. AI integration

`ai_service.get_or_generate_commentary()` gains an optional `headlines: list[str] | None`.
When present, the prompt gains one line:

> "Recent headlines: <…>. Reference them only if they plausibly relate to the move."

Flow when generating commentary: news_service fetches/serves the day's articles →
the top-3 `is_top` titles are passed as `headlines` → one Groq call produces
news-aware commentary. Still cached per pair/date in `ai_commentary`.

## 7. Error handling & edge cases

All failures degrade gracefully; **news never breaks the dashboard**.

| Case | Behaviour |
|---|---|
| GDELT timeout / 5xx / empty | News section shows empty state ("No news found for this date"). Explainer runs **without** headlines (pure rate-based commentary). |
| Date older than ~3 months | Same empty state in v1; Alpha Vantage fallback in v2. |
| Dashboard date == today/latest | Query GDELT recent window (last 24–72h) instead of a fixed past day. |
| Partial/dup articles | Dedupe by URL per pair/date; cap list length (e.g. top 10). |

## 8. Frontend changes

- `api/endpoints.ts` — add `news(base, quote, date)`.
- `api/client.ts` — add `fetchNews(pair, date)` returning typed articles.
- `hooks/useNews.ts` — TanStack Query hook (mirrors `useCommentary`).
- `components/News.tsx` — new section: "Why it moved" (is_top) + "More news" list, each item a titled link with source + time.
- `App.tsx` — render `<News />` directly under `<MarketIntelligence />`.
- Loading / empty / error states match the existing card styling.

## 9. Testing (mirror existing `tests/` patterns)

- `test_gdelt.py` — mock `httpx` (like `test_frankfurter.py`); parse ArtList JSON, query building, language/country filters.
- `test_news_service.py` — cache hit/miss, refresh TTL for today, provider fallback chain, dedupe.
- `test_ai.py` — extend for the `headlines` arg (mock Groq, as it already does).
- Frontend: component renders the two layers; empty/error states.

## 10. Out of scope (v1)

- Alpha Vantage fallback (→ increment 2).
- AI-based headline reranking (provider ranking is enough for v1).
- Sentiment scoring / charts on news.
- Push/real-time updates (cache + TTL is enough).

## 11. Build approach

Implemented via subagent-driven development: **Opus 4.8 orchestrates and reviews;
Sonnet 4.6 subagents write code** against bounded tasks from the implementation
plan. Final plan task: write a feature doc capturing the implementation and the
subagent workflow used.

Increment order:
1. **v1** — GDELT provider + news_service + cache table + router + news-aware explainer + News section + tests.
2. **v2** — Alpha Vantage fallback provider behind the existing interface, for older dates.
