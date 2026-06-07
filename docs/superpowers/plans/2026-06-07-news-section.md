# News Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a date-aware FX News section to the dashboard, backed by the GDELT DOC 2.0 API, and make the existing AI explainer news-aware.

**Architecture:** A backend `news_service` fetches articles per pair+date through a provider chain (GDELT in v1), caches them in a new `news_articles` table (mirroring `ai_commentary`), and exposes them via `GET /api/v1/news/{base}/{quote}`. The AI explainer receives the top headlines so it can cite real events. A new React `News` section renders under `MarketIntelligence`.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, httpx, Groq; React 19 + TanStack Query (frontend). Tests: pytest with `monkeypatch`/`unittest.mock` (mock `httpx`/`Groq`).

**Scope:** v1 = GDELT only. Alpha Vantage fallback for older dates is **out of scope** (increment 2) but the provider interface is built to accept it.

---

## File Structure

**Backend (create):**
- `app/services/news_config.py` — pair→query mapping + constants.
- `app/services/news_providers/__init__.py`
- `app/services/news_providers/base.py` — `Article` dataclass + `NewsProvider` protocol.
- `app/services/news_providers/gdelt.py` — `GdeltProvider` (DOC 2.0 client).
- `app/services/news_service.py` — `get_or_fetch_news()` cache + chain + dedupe + is_top + TTL.
- `app/routers/news.py` — `GET /news/{base}/{quote}`.

**Backend (modify):**
- `app/models.py` — add `NewsArticle`.
- `app/schemas.py` — add `NewsArticleOut`, `NewsResponse`.
- `app/main.py` — register news router.
- `app/services/ai_service.py` — add optional `headlines` arg.
- `app/routers/ai.py` — fetch top headlines, pass to commentary.

**Frontend (create):** `src/hooks/useNews.ts`, `src/components/News.tsx`.
**Frontend (modify):** `src/api/endpoints.ts`, `src/api/client.ts`, `src/api/mocks/fixtures.ts`, `src/App.tsx`.

**Docs (create):** `docs/features/news-section.md`.

---

## Task 1: `NewsArticle` model + schemas

**Files:**
- Modify: `Backend/app/models.py`
- Modify: `Backend/app/schemas.py`
- Test: `Backend/tests/test_news_model.py`

- [ ] **Step 1: Write the failing test**

```python
# Backend/tests/test_news_model.py
from datetime import date, datetime
from app import models, schemas


def test_news_article_persists_and_serializes(db_session):
    art = models.NewsArticle(
        base_currency="EUR", quote_currency="USD", date=date(2026, 6, 5),
        title="ECB holds rates", url="https://example.com/a",
        source="example.com", published_at=datetime(2026, 6, 5, 12, 0, 0),
        language="english", relevance=0.9, is_top=True,
    )
    db_session.add(art)
    db_session.commit()

    row = db_session.query(models.NewsArticle).filter_by(base_currency="EUR").one()
    assert row.title == "ECB holds rates"
    assert row.is_top is True

    out = schemas.NewsArticleOut.model_validate(row)
    assert out.url == "https://example.com/a"
    assert out.is_top is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_news_model.py -v`
Expected: FAIL with `AttributeError: module 'app.models' has no attribute 'NewsArticle'`.

- [ ] **Step 3: Add the model**

In `Backend/app/models.py`, update the import line and append the class:

```python
from sqlalchemy import Column, Integer, Text, Float, Date, DateTime, Boolean, UniqueConstraint
```

```python
class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    base_currency = Column(Text, nullable=False)
    quote_currency = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    source = Column(Text, nullable=False, default="")
    published_at = Column(DateTime, nullable=True)
    language = Column(Text, nullable=False, default="")
    relevance = Column(Float, nullable=True)
    is_top = Column(Boolean, nullable=False, default=False)
    fetched_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "date", "url"),)
```

- [ ] **Step 4: Add the schemas**

In `Backend/app/schemas.py`, update the datetime import and append:

```python
from datetime import date, datetime
```

```python
class NewsArticleOut(BaseModel):
    title: str
    url: str
    source: str
    published_at: Optional[datetime]
    language: str
    is_top: bool
    model_config = _ORM_CONFIG


class NewsResponse(BaseModel):
    base: str
    quote: str
    date: date
    top: list[NewsArticleOut]
    more: list[NewsArticleOut]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_news_model.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add Backend/app/models.py Backend/app/schemas.py Backend/tests/test_news_model.py
git commit -m "feat: add NewsArticle model and news schemas"
```

---

## Task 2: Provider interface + pair→query config

**Files:**
- Create: `Backend/app/services/news_providers/__init__.py`
- Create: `Backend/app/services/news_providers/base.py`
- Create: `Backend/app/services/news_config.py`
- Test: `Backend/tests/test_news_config.py`

- [ ] **Step 1: Write the failing test**

```python
# Backend/tests/test_news_config.py
from datetime import datetime
from app.services.news_config import PAIR_QUERIES, MAX_ARTICLES, TOP_N
from app.services.news_providers.base import Article

SUPPORTED = [("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")]


def test_every_supported_pair_has_a_query():
    for pair in SUPPORTED:
        cfg = PAIR_QUERIES[pair]
        assert cfg["keywords"], f"{pair} missing keywords"
        assert cfg["languages"], f"{pair} missing languages"


def test_tnd_pairs_include_french():
    assert "french" in PAIR_QUERIES[("USD", "TND")]["languages"]
    assert "french" in PAIR_QUERIES[("EUR", "TND")]["languages"]


def test_constants_are_sane():
    assert TOP_N <= MAX_ARTICLES


def test_article_dataclass_constructs():
    a = Article(title="t", url="u", source="s",
                published_at=datetime(2026, 6, 5), language="english")
    assert a.relevance is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_news_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.news_config'`.

- [ ] **Step 3: Create the provider base**

```python
# Backend/app/services/news_providers/__init__.py
```
(empty file)

```python
# Backend/app/services/news_providers/base.py
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None
    language: str
    relevance: float | None = None


class NewsProvider(Protocol):
    name: str

    def fetch(self, base: str, quote: str, on_date: date) -> list[Article]:
        """Return articles for the pair on/around on_date. Raises on hard failure."""
        ...
```

- [ ] **Step 4: Create the config**

```python
# Backend/app/services/news_config.py
MAX_ARTICLES = 10
TOP_N = 3
TODAY_REFRESH_HOURS = 6

# Maps a currency pair to GDELT query inputs.
PAIR_QUERIES = {
    ("EUR", "USD"): {
        "keywords": ["euro dollar", "ECB", "Federal Reserve", "eurozone economy"],
        "countries": ["US", "EU"],
        "languages": ["english"],
    },
    ("GBP", "USD"): {
        "keywords": ["pound dollar", "sterling", "Bank of England"],
        "countries": ["US", "UK"],
        "languages": ["english"],
    },
    ("USD", "TND"): {
        "keywords": ["Tunisian dinar", "Tunisia economy", "Banque Centrale de Tunisie"],
        "countries": ["TN", "US"],
        "languages": ["english", "french"],
    },
    ("EUR", "TND"): {
        "keywords": ["Tunisian dinar euro", "Tunisia trade", "BCT Tunisia"],
        "countries": ["TN", "EU"],
        "languages": ["english", "french"],
    },
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_news_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add Backend/app/services/news_providers/ Backend/app/services/news_config.py Backend/tests/test_news_config.py
git commit -m "feat: add news provider interface and pair query config"
```

---

## Task 3: GDELT provider

**Files:**
- Create: `Backend/app/services/news_providers/gdelt.py`
- Test: `Backend/tests/test_gdelt.py`

GDELT DOC 2.0 endpoint: `https://api.gdeltproject.org/api/v2/doc/doc`, no key.
Response shape: `{"articles": [{"url","title","seendate","domain","language","sourcecountry"}, ...]}`.
`seendate` format: `YYYYMMDDTHHMMSSZ`. For a past date we set `startdatetime`/`enddatetime`; for today/future we use a recent `timespan`.

- [ ] **Step 1: Write the failing test**

```python
# Backend/tests/test_gdelt.py
from datetime import date
from unittest.mock import patch, MagicMock
from app.services.news_providers.gdelt import GdeltProvider


def _resp(articles):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"articles": articles}
    return m


def test_fetch_parses_articles():
    sample = [{
        "url": "https://reuters.com/x", "title": "ECB holds rates",
        "seendate": "20260605T120000Z", "domain": "reuters.com",
        "language": "English", "sourcecountry": "United States",
    }]
    with patch("httpx.get", return_value=_resp(sample)) as g:
        arts = GdeltProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert len(arts) == 1
    assert arts[0].title == "ECB holds rates"
    assert arts[0].source == "reuters.com"
    assert arts[0].published_at is not None
    # query string carries a keyword and a language filter
    sent = g.call_args.kwargs["params"]["query"]
    assert "ECB" in sent
    assert "sourcelang:english" in sent


def test_fetch_empty_returns_empty_list():
    with patch("httpx.get", return_value=_resp([])):
        arts = GdeltProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert arts == []


def test_fetch_uses_timespan_for_today():
    with patch("httpx.get", return_value=_resp([])) as g:
        GdeltProvider().fetch("EUR", "USD", date.today())
    params = g.call_args.kwargs["params"]
    assert "timespan" in params
    assert "startdatetime" not in params
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_gdelt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.news_providers.gdelt'`.

- [ ] **Step 3: Implement the provider**

```python
# Backend/app/services/news_providers/gdelt.py
import httpx
from datetime import date, datetime
from app.services.news_config import PAIR_QUERIES, MAX_ARTICLES
from app.services.news_providers.base import Article

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _build_query(cfg: dict) -> str:
    keywords = " OR ".join(f'"{k}"' for k in cfg["keywords"])
    langs = " OR ".join(f"sourcelang:{lang}" for lang in cfg["languages"])
    return f"({keywords}) ({langs})"


def _parse_seendate(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ")
    except (ValueError, TypeError):
        return None


class GdeltProvider:
    name = "gdelt"

    def fetch(self, base: str, quote: str, on_date: date) -> list[Article]:
        cfg = PAIR_QUERIES[(base, quote)]
        params = {
            "query": _build_query(cfg),
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(MAX_ARTICLES),
            "sort": "HybridRel",
        }
        if on_date >= date.today():
            params["timespan"] = "3d"
        else:
            params["startdatetime"] = on_date.strftime("%Y%m%d000000")
            params["enddatetime"] = on_date.strftime("%Y%m%d235959")

        resp = httpx.get(GDELT_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        articles: list[Article] = []
        for i, a in enumerate(data.get("articles", [])):
            url = a.get("url")
            title = a.get("title")
            if not url or not title:
                continue
            articles.append(Article(
                title=title,
                url=url,
                source=a.get("domain", ""),
                published_at=_parse_seendate(a.get("seendate", "")),
                language=(a.get("language") or "").lower(),
                relevance=1.0 - i / MAX_ARTICLES,  # rank-based, GDELT pre-sorts by relevance
            ))
        return articles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_gdelt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/news_providers/gdelt.py Backend/tests/test_gdelt.py
git commit -m "feat: add GDELT DOC 2.0 news provider"
```

---

## Task 4: `news_service` — cache, chain, dedupe, is_top, TTL

**Files:**
- Create: `Backend/app/services/news_service.py`
- Test: `Backend/tests/test_news_service.py`

- [ ] **Step 1: Write the failing test**

```python
# Backend/tests/test_news_service.py
from datetime import date, datetime, timedelta
from app import models
from app.services import news_service
from app.services.news_providers.base import Article


def _arts(n):
    return [Article(title=f"t{i}", url=f"https://x/{i}", source="x",
                    published_at=datetime(2026, 6, 5), language="english",
                    relevance=1.0 - i * 0.1) for i in range(n)]


class FakeProvider:
    name = "fake"
    def __init__(self, arts): self.arts = arts; self.calls = 0
    def fetch(self, base, quote, on_date): self.calls += 1; return self.arts


def test_fetch_on_miss_then_cache_on_hit(db_session):
    p = FakeProvider(_arts(5))
    out1 = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    out2 = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert len(out1) == 5
    assert p.calls == 1  # second call served from cache


def test_top_n_marked(db_session):
    p = FakeProvider(_arts(5))
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert sum(1 for a in out if a.is_top) == news_service.TOP_N


def test_dedupes_by_url(db_session):
    dupes = _arts(3) + _arts(3)  # same urls twice
    p = FakeProvider(dupes)
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert len({a.url for a in out}) == len(out) == 3


def test_provider_chain_falls_back(db_session):
    class Boom:
        name = "boom"
        def fetch(self, *a): raise RuntimeError("down")
    good = FakeProvider(_arts(2))
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[Boom(), good])
    assert len(out) == 2


def test_today_refetches_when_stale(db_session):
    p = FakeProvider(_arts(2))
    today = date.today()
    news_service.get_or_fetch_news(db_session, "EUR", "USD", today, providers=[p])
    # age the cached rows past the refresh window
    for row in db_session.query(models.NewsArticle).all():
        row.fetched_at = datetime.utcnow() - timedelta(hours=news_service.TODAY_REFRESH_HOURS + 1)
    db_session.commit()
    news_service.get_or_fetch_news(db_session, "EUR", "USD", today, providers=[p])
    assert p.calls == 2  # refetched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_news_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.news_service'`.

- [ ] **Step 3: Implement the service**

```python
# Backend/app/services/news_service.py
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app import models
from app.services.news_config import TOP_N, TODAY_REFRESH_HOURS
from app.services.news_providers.gdelt import GdeltProvider

DEFAULT_PROVIDERS = [GdeltProvider()]


def _cached(db: Session, base: str, quote: str, on_date: date) -> list[models.NewsArticle]:
    return (
        db.query(models.NewsArticle)
        .filter_by(base_currency=base, quote_currency=quote, date=on_date)
        .order_by(models.NewsArticle.is_top.desc(), models.NewsArticle.relevance.desc())
        .all()
    )


def _is_fresh(rows: list[models.NewsArticle], on_date: date) -> bool:
    if not rows:
        return False
    if on_date < date.today():
        return True  # past news never changes
    newest = max((r.fetched_at for r in rows if r.fetched_at), default=None)
    if newest is None:
        return False
    return datetime.utcnow() - newest < timedelta(hours=TODAY_REFRESH_HOURS)


def _store(db: Session, base: str, quote: str, on_date: date, articles) -> None:
    # replace existing rows for this pair/date (handles today-refresh + dedupe)
    db.query(models.NewsArticle).filter_by(
        base_currency=base, quote_currency=quote, date=on_date
    ).delete()
    seen: set[str] = set()
    rank = 0
    for a in articles:
        if a.url in seen:
            continue
        seen.add(a.url)
        db.add(models.NewsArticle(
            base_currency=base, quote_currency=quote, date=on_date,
            title=a.title, url=a.url, source=a.source,
            published_at=a.published_at, language=a.language,
            relevance=a.relevance, is_top=(rank < TOP_N),
        ))
        rank += 1
    db.commit()


def get_or_fetch_news(db: Session, base: str, quote: str, on_date: date, providers=None):
    providers = providers if providers is not None else DEFAULT_PROVIDERS
    cached = _cached(db, base, quote, on_date)
    if _is_fresh(cached, on_date):
        return cached

    fetched = []
    for provider in providers:
        try:
            fetched = provider.fetch(base, quote, on_date)
        except Exception:
            fetched = []
        if fetched:
            break

    if not fetched:
        return cached  # may be [] — degrade gracefully

    _store(db, base, quote, on_date, fetched)
    return _cached(db, base, quote, on_date)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_news_service.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/news_service.py Backend/tests/test_news_service.py
git commit -m "feat: add news_service with cache, provider chain, dedupe, TTL"
```

---

## Task 5: News router

**Files:**
- Create: `Backend/app/routers/news.py`
- Modify: `Backend/app/main.py`
- Test: `Backend/tests/test_news_route.py`

- [ ] **Step 1: Write the failing test**

```python
# Backend/tests/test_news_route.py
from unittest.mock import patch
from datetime import datetime
from app.services.news_providers.base import Article


def _arts(n):
    return [Article(title=f"t{i}", url=f"https://x/{i}", source="x",
                    published_at=datetime(2026, 6, 5), language="english",
                    relevance=1.0 - i * 0.1) for i in range(n)]


def test_news_route_returns_top_and_more(client):
    with patch("app.services.news_service.DEFAULT_PROVIDERS",
               [type("P", (), {"name": "f", "fetch": lambda self, b, q, d: _arts(5)})()]):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["top"]) == 3
    assert len(data["more"]) == 2
    assert data["top"][0]["is_top"] is True


def test_news_route_rejects_bad_pair(client):
    resp = client.get("/api/v1/news/XXX/YYY?date=2026-06-05")
    assert resp.status_code == 400


def test_news_route_empty_when_no_articles(client):
    with patch("app.services.news_service.DEFAULT_PROVIDERS",
               [type("P", (), {"name": "f", "fetch": lambda self, b, q, d: []})()]):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    assert resp.json()["top"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_news_route.py -v`
Expected: FAIL with 404 (route not registered).

- [ ] **Step 3: Create the router**

```python
# Backend/app/routers/news.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app import schemas
from app.services import news_service
from app.routers.rates import _validate_pair

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/{base}/{quote}", response_model=schemas.NewsResponse)
def get_news(
    base: str,
    quote: str,
    date_param: date = Query(alias="date", default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    articles = news_service.get_or_fetch_news(db, base, quote, date_param)
    top = [a for a in articles if a.is_top]
    more = [a for a in articles if not a.is_top]
    return schemas.NewsResponse(base=base, quote=quote, date=date_param, top=top, more=more)
```

- [ ] **Step 4: Register the router**

In `Backend/app/main.py`, add `news` to the import and registration:

```python
from app.routers import currencies, rates, alerts, analysis, ai, news
```

```python
app.include_router(news.router, prefix="/api/v1")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_news_route.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add Backend/app/routers/news.py Backend/app/main.py Backend/tests/test_news_route.py
git commit -m "feat: add GET /news/{base}/{quote} endpoint"
```

---

## Task 6: News-aware AI explainer

**Files:**
- Modify: `Backend/app/services/ai_service.py`
- Modify: `Backend/app/routers/ai.py`
- Test: `Backend/tests/test_ai.py` (extend; keep existing tests offline)

- [ ] **Step 1: Write the failing test (and patch existing tests for offline news)**

Add to `Backend/tests/test_ai.py`:

```python
def test_commentary_includes_headlines_in_prompt(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)

    captured = {}
    mock_groq = MagicMock()
    def capture(**kwargs):
        captured["messages"] = kwargs["messages"]
        r = MagicMock()
        r.choices[0].message.content = "Dinar steady amid IMF talks."
        return r
    mock_groq.chat.completions.create.side_effect = capture

    fake_headlines = [type("A", (), {"title": "IMF approves Tunisia loan", "is_top": True})()]
    with patch("app.routers.ai.news_service.get_or_fetch_news", return_value=fake_headlines), \
         patch("app.services.ai_service.Groq", return_value=mock_groq):
        resp = client.post("/api/v1/ai/commentary", json={
            "base": "USD", "quote": "TND", "date": "2024-01-09"
        })

    assert resp.status_code == 200
    prompt = captured["messages"][0]["content"]
    assert "IMF approves Tunisia loan" in prompt
```

Also patch the THREE existing tests so they stay offline — wrap each existing
`client.post("/api/v1/ai/commentary", ...)` call site by adding this patch around it:

```python
    with patch("app.routers.ai.news_service.get_or_fetch_news", return_value=[]):
        # ... existing client.post(...) call goes inside this block ...
```

(Apply to `test_commentary_returns_text`, `test_commentary_is_cached_on_second_call`,
and `test_commentary_returns_502_on_groq_failure`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_ai.py -v`
Expected: FAIL — `news_service` not imported in `app.routers.ai`, and headlines not in prompt.

- [ ] **Step 3: Add the `headlines` arg to ai_service**

In `Backend/app/services/ai_service.py`, change the signature and prompt. Replace:

```python
def get_or_generate_commentary(
    db: Session, base: str, quote: str, target_date: date
) -> tuple[str, bool]:
```

with:

```python
def get_or_generate_commentary(
    db: Session, base: str, quote: str, target_date: date,
    headlines: list[str] | None = None,
) -> tuple[str, bool]:
```

Then, immediately after the existing `prompt = (...)` assignment, append:

```python
    if headlines:
        joined = "; ".join(headlines[:3])
        prompt += (
            f" Recent headlines: {joined}. "
            f"Reference them only if they plausibly relate to the move."
        )
```

- [ ] **Step 4: Wire the router to fetch + pass headlines**

In `Backend/app/routers/ai.py`, add the import:

```python
from app.services import ai_service, news_service
```

Replace the commentary call block:

```python
    try:
        commentary, cached = ai_service.get_or_generate_commentary(db, base, quote, body.date)
```

with:

```python
    try:
        articles = news_service.get_or_fetch_news(db, base, quote, body.date)
        headlines = [a.title for a in articles if getattr(a, "is_top", False)]
    except Exception:
        headlines = []
    try:
        commentary, cached = ai_service.get_or_generate_commentary(
            db, base, quote, body.date, headlines=headlines
        )
```

(Keep the existing `except ValueError` / `except Exception` handlers below it unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd Backend && pytest tests/test_ai.py -v`
Expected: PASS (4 tests, including the new one).

- [ ] **Step 6: Run the full backend suite**

Run: `cd Backend && pytest -q`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add Backend/app/services/ai_service.py Backend/app/routers/ai.py Backend/tests/test_ai.py
git commit -m "feat: make AI explainer news-aware via top headlines"
```

---

## Task 7: Frontend News section

**Files:**
- Modify: `frontend/src/api/endpoints.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/mocks/fixtures.ts`
- Create: `frontend/src/hooks/useNews.ts`
- Create: `frontend/src/components/News.tsx`
- Modify: `frontend/src/App.tsx`

No automated frontend tests exist in this repo; verification is `tsc` build + manual load.

- [ ] **Step 1: Add the endpoint**

In `frontend/src/api/endpoints.ts`, add to the `endpoints` object:

```ts
  news: (b: string, q: string, date: string) =>
    `${BASE}/news/${b}/${q}?date=${date}`,
```

- [ ] **Step 2: Add types + client function**

In `frontend/src/api/client.ts`, add near the other interfaces:

```ts
export interface NewsArticle {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  language: string;
  is_top: boolean;
}
export interface NewsResponse {
  base: string;
  quote: string;
  date: string;
  top: NewsArticle[];
  more: NewsArticle[];
}
```

And add the fetch function (mirrors `fetchCommentary`):

```ts
/** News for a pair on a given day (top + more). */
export async function fetchNews(pair: string, day: string): Promise<NewsResponse> {
  if (USE_MOCKS) return fixtures.news(pair, day);
  const { base, quote } = splitPair(pair);
  return jget<NewsResponse>(endpoints.news(base, quote, day));
}
```

- [ ] **Step 3: Add a mock fixture**

In `frontend/src/api/mocks/fixtures.ts`, add a `news` function to the `fixtures` object so `VITE_USE_MOCKS=true` still runs:

```ts
  news(pair: string, day: string) {
    return {
      base: pair.split('/')[0],
      quote: pair.split('/')[1],
      date: day,
      top: [
        { title: `${pair} steadies as central banks hold`, url: 'https://example.com/1',
          source: 'example.com', published_at: `${day}T10:00:00`, language: 'english', is_top: true },
      ],
      more: [
        { title: `Markets weigh ${pair} outlook`, url: 'https://example.com/2',
          source: 'example.com', published_at: `${day}T08:00:00`, language: 'english', is_top: false },
      ],
    };
  },
```

- [ ] **Step 4: Add the hook**

```ts
// frontend/src/hooks/useNews.ts
import { useQuery } from '@tanstack/react-query';
import { fetchNews } from '../api/client';
import { isoDay } from '../lib/dates';

/** News for a pair on the latest dashboard date. Mirrors useCommentary. */
export function useNews(pair: string) {
  const day = isoDay(new Date());
  return useQuery({
    queryKey: ['news', pair, day],
    queryFn: () => fetchNews(pair, day),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
```

- [ ] **Step 5: Add the News component**

```tsx
// frontend/src/components/News.tsx
import { useNews } from '../hooks/useNews';
import { type Pair } from '../lib/constants';
import type { NewsArticle } from '../api/client';
import { Card, CardHead } from './ui';

function Item({ a }: { a: NewsArticle }) {
  return (
    <li className="news-item">
      <a href={a.url} target="_blank" rel="noopener noreferrer">{a.title}</a>
      <span className="news-meta mono">{a.source}</span>
    </li>
  );
}

export function News({ pair }: { pair: Pair }) {
  const { data, isLoading, isError } = useNews(pair);
  const top = data?.top ?? [];
  const more = data?.more ?? [];
  const empty = !isLoading && !isError && top.length === 0 && more.length === 0;

  return (
    <Card className="news-card">
      <CardHead title="News" hint={`Relevant headlines for ${pair}`} />
      {isLoading && <p className="news-status">Loading news…</p>}
      {isError && <p className="news-status">News is temporarily unavailable.</p>}
      {empty && <p className="news-status">No news found for this date.</p>}
      {top.length > 0 && (
        <>
          <h4 className="news-subhead">Why it moved</h4>
          <ul className="news-list">{top.map((a) => <Item key={a.url} a={a} />)}</ul>
        </>
      )}
      {more.length > 0 && (
        <>
          <h4 className="news-subhead">More news</h4>
          <ul className="news-list">{more.map((a) => <Item key={a.url} a={a} />)}</ul>
        </>
      )}
    </Card>
  );
}
```

- [ ] **Step 6: Render it under Market Intelligence**

In `frontend/src/App.tsx`, add the import:

```tsx
import { News } from './components/News';
```

And add the component directly after `<MarketIntelligence ... />`:

```tsx
        <MarketIntelligence pair={pair} now={now} />
        <News pair={pair} />
```

- [ ] **Step 7: Verify the build**

Run: `cd frontend && npm run build`
Expected: `tsc` + Vite build succeed with no type errors.

- [ ] **Step 8: Manual check**

Start backend (`cd Backend && uvicorn app.main:app --reload --port 8000`) and frontend
(`cd frontend && npm run dev`), open http://127.0.0.1:5174, and confirm a News card
renders under Market Intelligence with headlines (or a graceful empty/error state).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/endpoints.ts frontend/src/api/client.ts frontend/src/api/mocks/fixtures.ts frontend/src/hooks/useNews.ts frontend/src/components/News.tsx frontend/src/App.tsx
git commit -m "feat: add News section under Market Intelligence"
```

---

## Task 8: Feature documentation

**Files:**
- Create: `docs/features/news-section.md`

- [ ] **Step 1: Write the doc**

Create `docs/features/news-section.md` covering:
- **What it does** — the News section (Why it moved / More news) and the news-aware AI explainer.
- **Data source** — GDELT DOC 2.0 (free, no key, ~3-month window); Alpha Vantage fallback noted as planned increment 2.
- **Backend flow** — `news_service.get_or_fetch_news` → provider chain → `news_articles` cache (per pair/date, today TTL ~6h) → router → AI explainer headlines.
- **Pair→query mapping** — the keyword/country/language table, including French for TND pairs.
- **Frontend** — `useNews` hook + `News` component rendered under `MarketIntelligence`.
- **Limitations** — ~3-month history; TND coverage; graceful degradation.
- **How we built it** — subagent-driven development: Opus 4.8 orchestrated and reviewed; Sonnet 4.6 subagents implemented each task TDD-first; reference this plan and the spec at `docs/superpowers/specs/2026-06-07-news-section-design.md`.

- [ ] **Step 2: Commit**

```bash
git add docs/features/news-section.md
git commit -m "docs: document the news section feature and build process"
```

---

## Definition of Done

- [ ] `cd Backend && pytest -q` passes (new: model, config, gdelt, news_service, news_route; extended: ai).
- [ ] `cd frontend && npm run build` passes with no type errors.
- [ ] News section renders under Market Intelligence with graceful empty/error states.
- [ ] AI explainer references headlines when present.
- [ ] Feature doc written.
- [ ] All work committed on `feature/news-section`.
