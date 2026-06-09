# News Section — Feature Documentation

**Feature:** Date-aware FX News with Per-article AI Explanations
**Status:** Implemented (v1 — GDELT provider + Groq enrichment)
**Related docs:** [`docs/superpowers/specs/2026-06-07-news-section-design.md`](../superpowers/specs/2026-06-07-news-section-design.md), [`docs/superpowers/plans/2026-06-07-news-section.md`](../superpowers/plans/2026-06-07-news-section.md)

---

## 1. Overview

The News feature adds a **News section** to the Colombus FX dashboard, rendered below Market Intelligence. It shows articles relevant to the selected currency pair and date, in two layers:

- **Why it moved** — the top 2–3 most relevant articles (`is_top` items), each displayed as a **Groq-written paragraph** explaining the article and how it relates to the pair's price move. The **source is shown as a clickable link beneath** the paragraph.
- **More news** — the remaining articles for broader context, shown as plain headline links.

**Market Intelligence** (the existing AI explainer) is a **purely rate-based AI commentary**. An earlier change that made it news-aware by appending headlines to the Groq prompt was **reverted**. Market Intelligence now contains no news-fetching logic. The News section is the place where AI explains the news.

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
        │     └─ Yes, and cache is fresh → return cached rows (with stored explanations)
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
                    │
                    ▼
              _enrich_top(db, articles, base, quote, on_date)
              (runs only on a cache miss, for the top-3 is_top articles)
              │
              ├─ _rate_context(base, quote, on_date) — best-effort daily %/risk context
              │
              └─ For each top article:
                    ├─ article_fetcher.fetch_article_text(url)
                    │     Scrapes <p> text via httpx + lxml, capped ~3000 chars
                    │     Returns None on any network/parse failure
                    │
                    ├─ news_explainer.explain_article(title, text, rate_context)
                    │     Sends article text (or headline if text is None) to Groq
                    │     Returns a paragraph string, or None if Groq call fails
                    │
                    └─ Stores paragraph in explanation column of news_articles
                          (null if Groq failed → item displayed as plain link)
                    │
                    ▼
              Return {top: [...], more: [...]}
```

### Enrichment details

- `app/services/article_fetcher.py` — fetches a URL with `httpx`, parses `<p>` tags with `lxml`, concatenates text up to ~3000 characters, and returns `None` on any failure (network error, parse error, timeout). It never raises.
- `app/services/news_explainer.py` — takes a title, optional article body text, and a rate context string, calls Groq to produce a short explanatory paragraph, and returns `None` if the Groq call fails. Falls back to generating the paragraph from the headline alone when body text is `None`.
- `_rate_context` in `news_service.py` — best-effort: queries the rates table for the pair's daily change and appends a brief context string to the Groq prompt. If rate data is unavailable the context is omitted; enrichment still proceeds.
- Enrichment runs **only on a cache miss**. Cached loads serve the `explanation` values already stored in the database. Past dates are cached permanently; today's news refreshes every ~6 hours.

### AI explainer (Market Intelligence) — rate-only

`routers/ai.py` calls `ai_service.get_or_generate_commentary(...)` with rate data only. No news-fetching or headline-appending logic is present. This path was reverted from the earlier news-aware version.

### Caching rules

| Scenario | Behaviour |
|---|---|
| Past date (not today) | Cached permanently after the first fetch. Providers and enrichment are never called again for the same pair+date. |
| Today | Cached with a **6-hour TTL** (`TODAY_REFRESH_HOURS=6`). Stale rows are re-fetched and re-enriched. |
| Provider failure | Returns whatever is cached (may be empty). Dashboard degrades gracefully; no error is surfaced as a crash. |
| Article scrape failure | Explanation is generated from headline only (no body text passed to Groq). |
| Groq call failure | `explanation` column is left `null`; that item is displayed as a plain headline link on the frontend. |

### Performance note

On a **cache miss**, the first load for a pair+date is slow — approximately **10–15 seconds** — because the backend scrapes up to 3 article pages sequentially and makes 3 separate Groq calls. Once cached, all subsequent loads are fast (database reads only). Past dates are cached permanently; today's data refreshes at most once every 6 hours.

---

## 4. Data Model

### `news_articles` table

The `news_articles` table gained an `explanation` column in this refinement:

| Column | Type | Notes |
|---|---|---|
| `explanation` | `Text`, nullable | Groq-written paragraph for `is_top` articles. `null` for non-top articles or when Groq failed. |

All existing columns (url, title, source, published_at, language, relevance, is_top, base, quote, on_date, fetched_at) are unchanged.

### `NewsArticleOut` schema

`NewsArticleOut` gained `explanation: Optional[str]`. Non-top articles always have `explanation: null`.

---

## 5. Pair → Query Mapping

Defined in `app/services/news_config.py` (`PAIR_QUERIES`). Each entry contains GDELT query keywords, a country filter, and languages.

| Pair | Keywords (summary) | Countries | Languages |
|---|---|---|---|
| USD/EUR | `"US dollar euro exchange rate"`, `"forex USD EUR"` | US, Germany, France, ECB | English |
| EUR/USD | Same as USD/EUR (symmetric) | US, Germany, France, ECB | English |
| USD/TND | `"Tunisian dinar dollar"`, `"taux de change dinar"`, `"BCT banque centrale tunisie"` | Tunisia, US | **English + French** |
| EUR/TND | `"Tunisian dinar euro"`, `"dinar tunisien euro"`, `"BCT banque centrale"` | Tunisia, Europe | **English + French** |

**Why French for TND pairs?** The majority of Tunisian economic and central-bank coverage is published in French. Without French, GDELT results for USD/TND and EUR/TND would be severely under-representative. The French keywords are set alongside English ones in the same query.

---

## 6. API

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
      "relevance": 0.92,
      "explanation": "Tunisia's central bank held its benchmark rate steady on Thursday despite rising dollar pressure, signalling confidence in the dinar's near-term stability. The decision limits the immediate upward movement in USD/TND that a rate cut might have triggered."
    },
    {
      "title": "Tunisian dinar edges lower as US dollar strengthens",
      "url": "https://example.com/article2",
      "source": "Reuters",
      "published_at": "2026-06-07T08:15:00",
      "language": "en",
      "relevance": 0.87,
      "explanation": "A broad dollar rally fuelled by stronger-than-expected US jobs data pushed the dinar lower across the session. With Tunisia's reserves providing limited buffer, the pair extended its weekly gain."
    }
  ],
  "more": [
    {
      "title": "Tunisia foreign reserves stable in May",
      "url": "https://example.com/article3",
      "source": "TAP",
      "published_at": "2026-06-06T14:00:00",
      "language": "en",
      "relevance": 0.61,
      "explanation": null
    }
  ]
}
```

`top` contains `is_top` articles (up to `TOP_N=3`), each with an `explanation` paragraph (or `null` if Groq failed). `more` contains the remaining articles with `explanation: null`. Both arrays may be empty.

---

## 7. Frontend

### API layer

- `src/api/endpoints.ts` — defines the `fetchNews(base, quote, date)` function.
- `src/api/client.ts` — exports `NewsArticle` (including the `explanation?: string | null` field) and `NewsResponse` TypeScript types.
- `src/api/mocks/fixtures.ts` — contains a `news` fixture so the UI works with `VITE_USE_MOCKS=true` during offline development.

### Hook

`src/hooks/useNews.ts` — a TanStack Query hook. Accepts `base`, `quote`, and `date` (always the latest/currently shown date). Returns `{ data, isLoading, isError }`. Caching and background refetch are handled by TanStack Query.

### Component

`src/components/News.tsx` — Renders the News card. Structure:
- **Loading state** — skeleton/spinner while the query is in flight.
- **Error state** — soft error message; does not crash the page.
- **Empty state** — shown when `top` and `more` are both empty (e.g., date is outside the 3-month GDELT window).
- **"Why it moved"** — renders each item in `top[]`. When `explanation` is non-null, the paragraph is shown as the primary content with the source rendered as a clickable link beneath it. When `explanation` is null, the item falls back to a plain headline link.
- **"More news"** — renders each item in `more[]` as plain headline links.

### Integration in App

In `src/App.tsx`, `<News>` is rendered immediately after `<MarketIntelligence>`, both inside the same column. They are siblings, not nested.

---

## 8. Configuration and Tuning

All tunable constants live in `app/services/news_config.py`.

| Constant | Default | Effect |
|---|---|---|
| `MAX_ARTICLES` | `10` | Maximum total articles fetched per provider call and stored in cache. Raise for more `more[]` items; raise cautiously as GDELT rate varies. |
| `TOP_N` | `3` | How many articles are marked `is_top`, returned in `top[]`, and enriched with Groq explanations. |
| `TODAY_REFRESH_HOURS` | `6` | How old today's cached rows can be before they are re-fetched and re-enriched. Lower for more up-to-date news; raises GDELT call and Groq call frequency. |

To change the query keywords, countries, or languages for a pair, edit the corresponding entry in the `PAIR_QUERIES` dict in `news_config.py`. No other file needs to change.

---

## 9. Limitations

**~3-month news window.** GDELT DOC 2.0 reliably serves only approximately the most recent 3 months of articles. Requests for older dates will return an empty `top[]` and `more[]`, and the frontend shows an empty state. The planned Alpha Vantage fallback (v2) will partially address this for major pairs.

**TND coverage on older dates.** Even after the Alpha Vantage fallback ships, USD/TND and EUR/TND coverage for historical dates will likely remain sparse. Alpha Vantage is US-market-centric and does not index Tunisian or French-language media well.

**Cold-load latency.** The first request for a pair+date (cache miss) takes ~10–15 seconds due to sequential article scraping and Groq calls. Subsequent requests are served from the database and are fast.

**Article scraping reliability.** `article_fetcher.py` performs best-effort scraping. Paywalled, JavaScript-rendered, or bot-protected pages will fail silently; those articles fall back to headline-only Groq explanations.

**Graceful degradation.** Every failure path in the backend is handled silently:
- A provider network error returns whatever is already cached (possibly empty).
- An article scrape failure causes the explanation to be generated from the headline only.
- A Groq explanation failure leaves `explanation` as `null`; the frontend shows a plain headline link.
- The frontend error state is a soft message, never a page crash.

**Market Intelligence is not news-aware.** The AI commentary in Market Intelligence uses only rate data. An earlier version that injected headlines into the prompt was reverted; news context is surfaced exclusively through the News section's per-article explanations.

**No real-time streaming.** News is fetched on demand and cached. The dashboard does not push new articles as they appear; users see freshened data after the 6-hour TTL expires or on a new page load for past dates.

---

## 10. Testing

### Backend test files

| File | What it covers |
|---|---|
| `Backend/tests/test_news_model.py` | `NewsArticle` SQLAlchemy model — create, query, uniqueness constraint on the cache key. |
| `Backend/tests/test_news_config.py` | `PAIR_QUERIES` structure, `Article` dataclass, constant values. |
| `Backend/tests/test_gdelt.py` | `GdeltProvider.fetch` — uses `httpx` mocks to test both the today path (timespan) and the past-date path (startdatetime/enddatetime), plus error handling. |
| `Backend/tests/test_article_fetcher.py` | `article_fetcher.fetch_article_text` — verifies text extraction from `<p>` tags, the ~3000-char cap, and silent failure on network/parse errors. |
| `Backend/tests/test_news_explainer.py` | `news_explainer.explain_article` — verifies paragraph generation with full body text, headline-only fallback when body is `None`, and `None` return on Groq failure. |
| `Backend/tests/test_news_service.py` | `get_or_fetch_news` — cache-first logic, deduplication, is_top marking, today TTL, graceful degradation on provider failure, and `_enrich_top` enrichment (with autouse offline fixture to prevent live Groq calls). |
| `Backend/tests/test_news_route.py` | `GET /api/v1/news/{base}/{quote}` — integration tests for the router, including the top/more split, `explanation` field presence, 422 on missing date, and autouse offline fixture so the live Groq API is never called in CI. |
| `Backend/tests/test_ai.py` | Rate-only AI commentary — verifies commentary generation from rate data; no headlines path (reverted). |

The full backend suite is **68 tests**. All pass.

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

## 11. How This Feature Was Built

The News feature was implemented using **subagent-driven development**, a structured multi-agent workflow:

- **Orchestrator (Claude Opus 4.8):** Wrote the design spec and implementation plan, broke the work into sequential tasks, dispatched each task to a dedicated subagent, and reviewed each result against the spec before dispatching the next.
- **Implementers (Claude Sonnet 4.6):** Each implementation task was handed to a fresh Sonnet 4.6 subagent. Each subagent worked **test-first (TDD)**: wrote failing tests, then implemented the code to make them pass, then verified. No shared state between subagents — each received only its task spec and the committed state of the branch.
- **Refinement round:** After the initial implementation, a second round of subagent tasks added per-article Groq enrichment (`article_fetcher`, `news_explainer`, `_enrich_top`), the `explanation` column, and reverted the news-aware Market Intelligence change. This doc was updated as the final task of the refinement.

This approach kept each subagent focused on a small, well-specified scope, made regressions detectable early (tests from task N are re-run in task N+1's environment), and allowed the orchestrator to course-correct between tasks without rewriting large amounts of code.

**Reference documents:**
- Design spec: [`docs/superpowers/specs/2026-06-07-news-section-design.md`](../superpowers/specs/2026-06-07-news-section-design.md)
- Implementation plan: [`docs/superpowers/plans/2026-06-07-news-section.md`](../superpowers/plans/2026-06-07-news-section.md)
