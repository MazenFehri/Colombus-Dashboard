# News Section — Feature Documentation

**Feature:** Date-aware FX News + News-aware AI Explainer
**Status:** Implemented (v1 — GDELT provider)
**Related docs:** [`docs/superpowers/specs/2026-06-07-news-section-design.md`](../superpowers/specs/2026-06-07-news-section-design.md), [`docs/superpowers/plans/2026-06-07-news-section.md`](../superpowers/plans/2026-06-07-news-section.md)

---

## 1. Overview

The News feature adds two distinct, independently-rendered sections to the Colombus FX dashboard:

**News section (new)** — Rendered below Market Intelligence. Shows articles relevant to the selected currency pair and date, in two layers:
- **Why it moved** — the top 2–3 most relevant headlines (`is_top` items), surfaced for users who want a quick answer.
- **More news** — the remaining articles for broader context.

**Market Intelligence (enhanced)** — The existing AI explainer. It now best-effort fetches the day's top headlines and appends them to the Groq prompt, so its commentary can cite real events. News failure never blocks the AI commentary from rendering.

The two sections are deliberately decoupled: the News section is served by its own endpoint (`GET /api/v1/news/...`), while Market Intelligence continues to use `GET /api/v1/ai/...`. They share no state on the frontend.

---

## 2. Data Source

### v1 — GDELT DOC 2.0 API

- **Endpoint:** `https://api.gdeltproject.org/api/v2/doc/doc`
- **Cost:** Free. No API key required. No daily request limit.
- **Coverage:** Global, including Tunisia. Reliable for roughly the **most recent 3 months** of news.
- **Query strategy:**
  - For today or future dates: `timespan=3d` (rolling 3-day window).
  - For past dates: `startdatetime` / `enddatetime` bounded to the requested day.
- **Response parsing:** The `ArtList` JSON array is parsed into `Article` dataclass instances.

### v2 — Alpha Vantage NEWS_SENTIMENT (planned, not yet implemented)

An Alpha Vantage fallback is designed to slot behind the same `NewsProvider` Protocol for dates outside GDELT's ~3-month window. This is **increment 2** and has not been built yet. When it lands, it will primarily rescue EUR/USD and GBP/USD history; older USD/TND and EUR/TND dates will likely remain sparse because Alpha Vantage is US-market-centric.

---

## 3. Backend Architecture

### Request flow

```
Frontend
  GET /api/v1/news/{base}/{quote}?date=YYYY-MM-DD
        │
        ▼
  routers/news.py
        │
        ▼
  services/news_service.get_or_fetch_news(db, base, quote, on_date)
        │
        ├─ Cache hit? (news_articles table, keyed by base+quote+date+url)
        │     └─ Yes, and cache is fresh → return cached rows
        │
        └─ Cache miss or stale (today-only TTL) → provider fallback chain
              │
              ├─ GdeltProvider.fetch(base, quote, on_date)   [v1, live]
              └─ AlphaVantageProvider (not yet implemented)  [v2, planned]
                    │
                    ▼
              Deduplicate by URL
              Mark top N as is_top
              Persist to news_articles table
              Return {top: [...], more: [...]}
```

### AI explainer integration

```
  routers/ai.py
        │
        ├─ Calls get_or_fetch_news(...) → extracts top headline titles
        │   (best-effort; news failure is caught and ignored)
        │
        └─ Calls ai_service.get_or_generate_commentary(..., headlines=[...])
                    │
                    └─ Headlines appended to Groq prompt
                       Commentary may cite real events
```

### Caching rules

| Scenario | Behaviour |
|---|---|
| Past date (not today) | Cached permanently after the first fetch. Providers are never called again for the same pair+date. |
| Today | Cached with a **6-hour TTL** (`TODAY_REFRESH_HOURS=6`). Stale rows are re-fetched from providers. |
| Provider failure | Returns whatever is cached (may be empty). Dashboard degrades gracefully; no error is surfaced as a crash. |

---

## 4. Pair → Query Mapping

Defined in `app/services/news_config.py` (`PAIR_QUERIES`). Each entry contains GDELT query keywords, a country filter, and languages.

| Pair | Keywords (summary) | Countries | Languages |
|---|---|---|---|
| USD/EUR | `"US dollar euro exchange rate"`, `"forex USD EUR"` | US, Germany, France, ECB | English |
| EUR/USD | Same as USD/EUR (symmetric) | US, Germany, France, ECB | English |
| USD/TND | `"Tunisian dinar dollar"`, `"taux de change dinar"`, `"BCT banque centrale tunisie"` | Tunisia, US | **English + French** |
| EUR/TND | `"Tunisian dinar euro"`, `"dinar tunisien euro"`, `"BCT banque centrale"` | Tunisia, Europe | **English + French** |

**Why French for TND pairs?** The majority of Tunisian economic and central-bank coverage is published in French. Without French, GDELT results for USD/TND and EUR/TND would be severely under-representative. The French keywords are set alongside English ones in the same query.

---

## 5. API

### Endpoint

```
GET /api/v1/news/{base}/{quote}?date=YYYY-MM-DD
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `base` | path | Yes | Base currency code, e.g. `USD` |
| `quote` | path | Yes | Quote currency code, e.g. `TND` |
| `date` | query | Yes | Date in `YYYY-MM-DD` format |

### Example response

```json
{
  "base": "USD",
  "quote": "TND",
  "date": "2026-06-07",
  "top": [
    {
      "title": "BCT maintient son taux directeur face à la pression du dollar",
      "url": "https://example.com/article1",
      "source": "Kapitalis",
      "published_at": "2026-06-07T09:30:00",
      "language": "fr",
      "relevance": 0.92
    },
    {
      "title": "Tunisian dinar edges lower as US dollar strengthens",
      "url": "https://example.com/article2",
      "source": "Reuters",
      "published_at": "2026-06-07T08:15:00",
      "language": "en",
      "relevance": 0.87
    }
  ],
  "more": [
    {
      "title": "Tunisia foreign reserves stable in May",
      "url": "https://example.com/article3",
      "source": "TAP",
      "published_at": "2026-06-06T14:00:00",
      "language": "en",
      "relevance": 0.61
    }
  ]
}
```

`top` contains `is_top` articles (up to `TOP_N=3`). `more` contains the remaining articles. Both arrays may be empty.

---

## 6. Frontend

### API layer

- `src/api/endpoints.ts` — defines the `fetchNews(base, quote, date)` function.
- `src/api/client.ts` — exports `NewsArticle` and `NewsResponse` TypeScript types.
- `src/api/mocks/fixtures.ts` — contains a `news` fixture so the UI works with `VITE_USE_MOCKS=true` during offline development.

### Hook

`src/hooks/useNews.ts` — a TanStack Query hook. Accepts `base`, `quote`, and `date` (always the latest/currently shown date). Returns `{ data, isLoading, isError }`. Caching and background refetch are handled by TanStack Query.

### Component

`src/components/News.tsx` — Renders the News card. Structure:
- **Loading state** — skeleton/spinner while the query is in flight.
- **Error state** — soft error message; does not crash the page.
- **Empty state** — shown when `top` and `more` are both empty (e.g., date is outside the 3-month GDELT window).
- **"Why it moved"** — renders each item in `top[]`.
- **"More news"** — renders each item in `more[]`.

### Integration in App

In `src/App.tsx`, `<News>` is rendered immediately after `<MarketIntelligence>`, both inside the same column. They are siblings, not nested.

---

## 7. Configuration and Tuning

All tunable constants live in `app/services/news_config.py`.

| Constant | Default | Effect |
|---|---|---|
| `MAX_ARTICLES` | `10` | Maximum total articles fetched per provider call and stored in cache. Raise for more `more[]` items; raise cautiously as GDELT rate varies. |
| `TOP_N` | `3` | How many articles are marked `is_top` and returned in `top[]`. |
| `TODAY_REFRESH_HOURS` | `6` | How old today's cached rows can be before they are re-fetched. Lower for more up-to-date news; raises GDELT call frequency. |

To change the query keywords, countries, or languages for a pair, edit the corresponding entry in the `PAIR_QUERIES` dict in `news_config.py`. No other file needs to change.

---

## 8. Limitations

**~3-month news window.** GDELT DOC 2.0 reliably serves only approximately the most recent 3 months of articles. Requests for older dates will return an empty `top[]` and `more[]`, and the frontend shows an empty state. The planned Alpha Vantage fallback (v2) will partially address this for major pairs.

**TND coverage on older dates.** Even after the Alpha Vantage fallback ships, USD/TND and EUR/TND coverage for historical dates will likely remain sparse. Alpha Vantage is US-market-centric and does not index Tunisian or French-language media well.

**Graceful degradation.** Every failure path in the backend is handled silently:
- A provider network error returns whatever is already cached (possibly empty).
- A news fetch failure inside the AI explainer is caught; commentary is generated without headlines.
- The frontend error state is a soft message, never a page crash.

**No real-time streaming.** News is fetched on demand and cached. The dashboard does not push new articles as they appear; users see freshened data after the 6-hour TTL expires or on a new page load for past dates.

---

## 9. Testing

### Backend test files

| File | What it covers |
|---|---|
| `Backend/tests/test_news_model.py` | `NewsArticle` SQLAlchemy model — create, query, uniqueness constraint on the cache key. |
| `Backend/tests/test_news_config.py` | `PAIR_QUERIES` structure, `Article` dataclass, constant values. |
| `Backend/tests/test_gdelt.py` | `GdeltProvider.fetch` — uses `httpx` mocks to test both the today path (timespan) and the past-date path (startdatetime/enddatetime), plus error handling. |
| `Backend/tests/test_news_service.py` | `get_or_fetch_news` — uses fake providers to verify cache-first logic, deduplication, is_top marking, today TTL, and graceful degradation on provider failure. |
| `Backend/tests/test_news_route.py` | `GET /api/v1/news/{base}/{quote}` — integration tests for the router, including the top/more split and 422 on missing date. |
| `Backend/tests/test_ai.py` | Extended to cover the headlines path — verifies that top headlines are passed to the prompt when available and that AI commentary still works when news fetch fails. |

The full backend suite is 60 tests. All pass.

### Running the tests

```bash
# Backend
cd Backend
pytest -q

# Frontend build check (type errors + bundler errors)
cd frontend
npm run build
```

---

## 10. How This Feature Was Built

The News feature was implemented using **subagent-driven development**, a structured multi-agent workflow:

- **Orchestrator (Claude Opus 4.8):** Wrote the design spec and implementation plan, broke the work into 8 sequential tasks, dispatched each task to a dedicated subagent, and reviewed each result against the spec before dispatching the next.
- **Implementers (Claude Sonnet 4.6):** Each of the 7 implementation tasks (tasks 1–7) was handed to a fresh Sonnet 4.6 subagent. Each subagent worked **test-first (TDD)**: wrote failing tests, then implemented the code to make them pass, then verified. No shared state between subagents — each received only its task spec and the committed state of the branch.
- **Task 8 (this doc):** Documentation, committed as the final task.

This approach kept each subagent focused on a small, well-specified scope, made regressions detectable early (tests from task N are re-run in task N+1's environment), and allowed the orchestrator to course-correct between tasks without rewriting large amounts of code.

**Reference documents:**
- Design spec: [`docs/superpowers/specs/2026-06-07-news-section-design.md`](../superpowers/specs/2026-06-07-news-section-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-06-07-news-section.md`](../superpowers/plans/2026-06-07-news-section.md)
