# Market Intelligence (News + Deeper Analytics) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the AI market commentary with keyless-RSS news headlines and computed signals (trend, volatility regime, momentum), surfacing the signals in the time-travel snapshot/UI.

**Architecture:** A new `news.py` service fetches and caches Google News RSS headlines per currency-tag per day (degrading to `[]` on any failure). New pure analytics functions (`calc_trend`, `calc_vol_regime`, `calc_momentum`) are folded into the existing `build_snapshot` (so they are time-travel aware) and assembled — together with the headlines — into a `MarketContext` dataclass that drives an enriched LLM prompt. The frontend shows a trend arrow + regime badge and lists the headlines under the commentary.

**Tech Stack:** FastAPI · SQLAlchemy · pandas/numpy · pytest (backend); React + TypeScript + Vite + @tanstack/react-query (frontend); `feedparser` (new) for RSS.

**Conventions:** Backend tests run from `Backend/`: `python -m pytest tests/<file> -v`. Frontend is verified with `npx tsc --noEmit` from `frontend/` (no JS test runner configured). Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

**Backend**
- Create `Backend/app/services/news.py` — RSS fetch/cache + `pair_to_tag`.
- Modify `Backend/app/models.py` — add `NewsItem` table.
- Modify `Backend/app/services/analytics.py` — add `calc_trend`, `calc_vol_regime`, `calc_momentum`; extend `build_snapshot`.
- Modify `Backend/app/schemas.py` — extend `SnapshotOut`; add `HeadlineOut`; extend `CommentaryOut`.
- Modify `Backend/app/services/ai_service.py` — `MarketContext`, `build_market_context`, `build_prompt`; refactor `get_or_generate_commentary`.
- Modify `Backend/app/routers/ai.py` — return headlines.
- Modify `Backend/requirements.txt` — add `feedparser`.
- Create `Backend/tests/test_news.py`; modify `Backend/tests/test_analytics.py`, `Backend/tests/test_ai.py`, `Backend/tests/test_analysis.py`.

**Frontend**
- Modify `frontend/src/api/client.ts` — snapshot fields; `fetchCommentary` returns `{commentary, headlines}`.
- Modify `frontend/src/hooks/useCommentary.ts` — return type.
- Create `frontend/src/components/SignalBadges.tsx` — trend arrow + regime pill.
- Modify `frontend/src/components/MarketIntelligence.tsx` — sources list.
- Modify `frontend/src/App.tsx` — render `SignalBadges`.
- Modify `frontend/src/components/ui/ui.css` — badge + sources styles.

---

## Task 1: NewsItem model + news service

**Files:**
- Modify: `Backend/requirements.txt`
- Modify: `Backend/app/models.py`
- Create: `Backend/app/services/news.py`
- Test: `Backend/tests/test_news.py`

- [ ] **Step 1: Add the dependency**

In `Backend/requirements.txt`, add after the `groq>=0.9` line:

```
feedparser>=6.0
```

Then install it: `cd Backend && pip install feedparser>=6.0`

- [ ] **Step 2: Add the `NewsItem` model**

In `Backend/app/models.py`, append (the imports `Column, Integer, Text, Date, DateTime, UniqueConstraint` and `func` already exist at the top):

```python
class NewsItem(Base):
    __tablename__ = "news_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pair_tag = Column(Text, nullable=False)        # "EURUSD" | "GBPUSD" | "TND"
    headline = Column(Text, nullable=False)
    source = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    published_at = Column(DateTime, nullable=True)
    fetched_date = Column(Date, nullable=False)    # dashboard date this was pulled for
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("pair_tag", "url", "fetched_date"),)
```

- [ ] **Step 3: Write the failing tests**

Create `Backend/tests/test_news.py`:

```python
import time
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch
from app.services import news
from app import models


def _struct(dt):
    return dt.timetuple()


def _fake_feed(entries):
    class Feed:
        def __init__(self, entries):
            self.entries = entries
    return Feed(entries)


def _entry(title, link, source, hours_ago):
    published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "title": title,
        "link": link,
        "source": {"title": source},
        "published_parsed": _struct(published),
    }


def test_pair_to_tag():
    assert news.pair_to_tag("EUR", "USD") == "EURUSD"
    assert news.pair_to_tag("GBP", "USD") == "GBPUSD"
    assert news.pair_to_tag("USD", "TND") == "TND"
    assert news.pair_to_tag("EUR", "TND") == "TND"


def test_get_headlines_fetches_caches_and_caps(db_session):
    entries = [
        _entry("Euro climbs vs dollar", "http://x/1", "Reuters", 2),
        _entry("ECB holds rates", "http://x/2", "Bloomberg", 5),
        _entry("Dollar mixed", "http://x/3", "FT", 10),
        _entry("Old news", "http://x/4", "AP", 100),  # >48h, excluded
    ]
    with patch("app.services.news.feedparser.parse", return_value=_fake_feed(entries)):
        result = news.get_headlines(db_session, "EURUSD", date(2024, 1, 9), limit=3)

    assert len(result) == 3
    assert result[0].headline == "Euro climbs vs dollar"
    assert all(r.pair_tag == "EURUSD" for r in result)
    # Persisted
    assert db_session.query(models.NewsItem).count() == 3


def test_get_headlines_uses_cache_on_second_call(db_session):
    entries = [_entry("Euro up", "http://x/1", "Reuters", 1)]
    with patch("app.services.news.feedparser.parse", return_value=_fake_feed(entries)) as p:
        news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
        news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
    assert p.call_count == 1  # second call served from DB


def test_get_headlines_returns_empty_on_failure(db_session):
    with patch("app.services.news.feedparser.parse", side_effect=Exception("network down")):
        result = news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
    assert result == []
    assert db_session.query(models.NewsItem).count() == 0
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd Backend && python -m pytest tests/test_news.py -v`
Expected: FAIL (`module app.services.news not found` / `pair_to_tag` undefined).

- [ ] **Step 5: Implement the news service**

Create `Backend/app/services/news.py`:

```python
import time
import feedparser
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote_plus
from sqlalchemy.orm import Session
from app import models

_TAG_QUERIES = {
    "EURUSD": "EUR USD exchange rate",
    "GBPUSD": "GBP USD pound dollar exchange rate",
    "TND": "Tunisian dinar OR BCT OR Tunisia economy",
}

_LOOKBACK_HOURS = 48


def pair_to_tag(base: str, quote: str) -> str:
    """Map a currency pair to a news tag. TND (either side) groups together."""
    if base == "TND" or quote == "TND":
        return "TND"
    return f"{base}{quote}"


def _feed_url(tag: str) -> str:
    query = _TAG_QUERIES.get(tag, tag)
    return (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


def _published(entry) -> datetime | None:
    pp = entry.get("published_parsed")
    if not pp:
        return None
    return datetime.fromtimestamp(time.mktime(pp), tz=timezone.utc)


def _source(entry) -> str:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def get_headlines(db: Session, tag: str, on_date: date, limit: int = 3) -> list[models.NewsItem]:
    """Cached-per-(tag, day) headlines. Never raises — returns [] on any failure."""
    cached = (
        db.query(models.NewsItem)
        .filter(models.NewsItem.pair_tag == tag, models.NewsItem.fetched_date == on_date)
        .order_by(models.NewsItem.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    if cached:
        return cached
    try:
        return _fetch_and_store(db, tag, on_date, limit)
    except Exception:
        db.rollback()
        return []


def _fetch_and_store(db: Session, tag: str, on_date: date, limit: int) -> list[models.NewsItem]:
    feed = feedparser.parse(_feed_url(tag))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)
    items: list[models.NewsItem] = []
    for entry in feed.entries:
        published = _published(entry)
        if published is not None and published < cutoff:
            continue
        headline = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not headline or not url:
            continue
        items.append(models.NewsItem(
            pair_tag=tag,
            headline=headline,
            source=_source(entry),
            url=url,
            published_at=published.replace(tzinfo=None) if published else None,
            fetched_date=on_date,
        ))
        if len(items) >= limit:
            break
    for it in items:
        db.add(it)
    db.commit()
    for it in items:
        db.refresh(it)
    return items
```

Note: `.nullslast()` is available on SQLAlchemy column expressions; if the installed version rejects it, use `.order_by(models.NewsItem.published_at.desc())`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd Backend && python -m pytest tests/test_news.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add Backend/requirements.txt Backend/app/models.py Backend/app/services/news.py Backend/tests/test_news.py
git commit -m "feat: keyless RSS news service + NewsItem cache

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Analytics signals (trend, volatility regime, momentum)

**Files:**
- Modify: `Backend/app/services/analytics.py`
- Test: `Backend/tests/test_analytics.py`

- [ ] **Step 1: Write the failing tests**

In `Backend/tests/test_analytics.py`, update the import line to include the new functions:

```python
from app.services.analytics import (
    calc_daily_change, calc_performance, calc_high_low,
    calc_volatility, is_spike, build_snapshot,
    calc_trend, calc_vol_regime, calc_momentum,
)
```

Then append these tests:

```python
def test_calc_trend_none_under_30_rows():
    df = make_df([3.0 + i * 0.01 for i in range(20)])
    assert calc_trend(df) is None


def test_calc_trend_bullish():
    # Rising series: recent MA7 above MA30
    df = make_df([3.0 + i * 0.02 for i in range(40)])
    result = calc_trend(df)
    assert result is not None
    assert result["direction"] == "bullish"
    assert result["ma7"] > result["ma30"]


def test_calc_trend_bearish():
    df = make_df([4.0 - i * 0.02 for i in range(40)])
    result = calc_trend(df)
    assert result["direction"] == "bearish"


def test_calc_trend_neutral_flat():
    df = make_df([3.0 for _ in range(40)])
    assert calc_trend(df)["direction"] == "neutral"


def test_calc_vol_regime_none_when_short():
    df = make_df([3.0 + i * 0.01 for i in range(50)])
    assert calc_vol_regime(df) is None


def test_calc_vol_regime_elevated():
    import numpy as np
    rng = np.random.default_rng(0)
    calm = list(3.0 + np.cumsum(rng.normal(0, 0.001, 110)))
    shock = [calm[-1] * (1 + x) for x in rng.normal(0, 0.05, 5)]
    df = make_df(calm + shock)
    assert calc_vol_regime(df) == "elevated"


def test_calc_momentum_none_when_short():
    assert calc_momentum(make_df([3.0, 3.1])) is None


def test_calc_momentum_value():
    # Accelerating move => positive momentum
    df = make_df([3.00, 3.01, 3.04])
    result = calc_momentum(df)
    assert result is not None
    assert result > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend && python -m pytest tests/test_analytics.py -k "trend or vol_regime or momentum" -v`
Expected: FAIL (functions undefined / ImportError).

- [ ] **Step 3: Implement the three functions**

In `Backend/app/services/analytics.py`, add after `calc_volatility` (and before `build_snapshot`):

```python
def calc_trend(df: pd.DataFrame) -> dict | None:
    """MA7 vs MA30 directional signal. None if < 30 rows."""
    if len(df) < 30:
        return None
    ma7 = float(df["rate"].tail(7).mean())
    ma30 = float(df["rate"].tail(30).mean())
    if ma30 == 0:
        return None
    spread = abs(ma7 - ma30) / ma30
    if spread < 0.001:
        direction = "neutral"
    elif ma7 > ma30:
        direction = "bullish"
    else:
        direction = "bearish"
    return {"direction": direction, "ma7": round(ma7, 6), "ma30": round(ma30, 6)}


def calc_vol_regime(df: pd.DataFrame) -> str | None:
    """Current 21d vol vs the 90-obs average of that rolling vol.

    elevated  > 1.5x average; compressed < 0.6x average; else normal.
    None when there are < 90 rolling-std observations or the average is 0.
    """
    pct = _normalized_returns(df)
    rolling = pct.rolling(21).std().dropna()
    if len(rolling) < 90:
        return None
    current = float(rolling.iloc[-1])
    avg = float(rolling.tail(90).mean())
    if avg == 0:
        return None
    if current > 1.5 * avg:
        return "elevated"
    if current < 0.6 * avg:
        return "compressed"
    return "normal"


def calc_momentum(df: pd.DataFrame) -> float | None:
    """Acceleration of the daily return: (today - yesterday) / |yesterday|.

    Returns None if < 3 rows or yesterday's return is ~0.
    """
    if len(df) < 3:
        return None
    pct = _normalized_returns(df) * 100
    if len(pct) < 2:
        return None
    today = float(pct.iloc[-1])
    yest = float(pct.iloc[-2])
    if abs(yest) < 1e-9:
        return None
    return round((today - yest) / abs(yest), 4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Backend && python -m pytest tests/test_analytics.py -k "trend or vol_regime or momentum" -v`
Expected: PASS. If `test_calc_vol_regime_elevated` is flaky on the random seed, it is deterministic via `default_rng(0)` — leave as-is.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/analytics.py Backend/tests/test_analytics.py
git commit -m "feat: trend, volatility-regime, and momentum signals

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Fold signals into build_snapshot + schema + endpoint

**Files:**
- Modify: `Backend/app/services/analytics.py` (`build_snapshot`)
- Modify: `Backend/app/schemas.py` (`SnapshotOut`)
- Test: `Backend/tests/test_analytics.py`, `Backend/tests/test_analysis.py`

- [ ] **Step 1: Write the failing tests**

In `Backend/tests/test_analytics.py`, append:

```python
def test_build_snapshot_includes_signals():
    df = make_df([3.0 + i * 0.01 for i in range(120)])
    snap = build_snapshot(df, date(2024, 1, 2) + timedelta(days=119), "USD")
    assert "trend" in snap and snap["trend"] in {"bullish", "bearish", "neutral"}
    assert "vol_regime" in snap and snap["vol_regime"] in {"elevated", "normal", "compressed"}
    assert "momentum" in snap  # float or None


def test_build_snapshot_signals_none_near_start():
    df = make_df([3.0, 3.01, 3.02, 3.03, 3.05])
    snap = build_snapshot(df, date(2024, 1, 2) + timedelta(days=4), "USD")
    assert snap["trend"] is None
    assert snap["vol_regime"] is None
```

In `Backend/tests/test_analysis.py`, find the snapshot endpoint test (a `GET .../snapshot` assertion) and add field checks. If unsure where, append this standalone test (it seeds its own data):

```python
from datetime import date, timedelta
from app import models


def test_snapshot_endpoint_returns_signal_fields(client, db_session):
    start = date(2024, 1, 1)
    for i in range(120):
        db_session.add(models.ExchangeRate(
            base_currency="EUR", quote_currency="USD",
            rate=1.08 + i * 0.0005, date=start + timedelta(days=i), source="test",
        ))
    db_session.commit()
    as_of = (start + timedelta(days=119)).isoformat()
    resp = client.get(f"/api/v1/analysis/EUR/USD/snapshot?as_of={as_of}")
    assert resp.status_code == 200
    body = resp.json()
    assert "trend" in body and "vol_regime" in body and "momentum" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend && python -m pytest tests/test_analytics.py -k build_snapshot_includes_signals tests/test_analysis.py -k snapshot_endpoint_returns_signal_fields -v`
Expected: FAIL (`KeyError`/missing fields).

- [ ] **Step 3: Extend `build_snapshot`**

In `Backend/app/services/analytics.py`, inside `build_snapshot`, after the `volatility` try/except block and before the `if d1 is not None:` risk block, add:

```python
    trend_info = calc_trend(sliced)
    trend = trend_info["direction"] if trend_info else None
    vol_regime = calc_vol_regime(sliced)
    momentum = calc_momentum(sliced)
```

Then extend the returned dict (add the three keys alongside the existing ones):

```python
    return {
        "resolved_date": resolved_date,
        "rate": rate,
        "d1": d1,
        "d7": d7,
        "d30": d30,
        "high": high,
        "low": low,
        "volatility": volatility,
        "trend": trend,
        "vol_regime": vol_regime,
        "momentum": momentum,
        "risk": risk,
    }
```

- [ ] **Step 4: Extend `SnapshotOut`**

In `Backend/app/schemas.py`, update `SnapshotOut` to add three optional fields (keep existing ones):

```python
class SnapshotOut(BaseModel):
    resolved_date: date
    rate: float
    d1: Optional[float]
    d7: Optional[float]
    d30: Optional[float]
    high: float
    low: float
    volatility: Optional[float]
    trend: Optional[str]
    vol_regime: Optional[str]
    momentum: Optional[float]
    risk: str
    model_config = _ORM_CONFIG
```

The endpoint (`app/routers/analysis.py`) builds `SnapshotOut(**snap)`, so no router change is needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd Backend && python -m pytest tests/test_analytics.py tests/test_analysis.py -v`
Expected: PASS (all, including pre-existing snapshot tests).

- [ ] **Step 6: Commit**

```bash
git add Backend/app/services/analytics.py Backend/app/schemas.py Backend/tests/test_analytics.py Backend/tests/test_analysis.py
git commit -m "feat: expose trend/regime/momentum in snapshot

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: MarketContext + enriched prompt + headlines in commentary

**Files:**
- Modify: `Backend/app/services/ai_service.py`
- Modify: `Backend/app/schemas.py` (`HeadlineOut`, `CommentaryOut`)
- Modify: `Backend/app/routers/ai.py`
- Test: `Backend/tests/test_ai.py`

- [ ] **Step 1: Write the failing tests**

In `Backend/tests/test_ai.py`, append:

```python
from app.services import ai_service, news as news_service


def test_build_prompt_includes_headlines_and_omits_none(db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)
    fake = [models.NewsItem(pair_tag="TND", headline="Dinar steady", source="TAP",
                            url="http://x/1", fetched_date=date(2024, 1, 9))]
    with patch("app.services.ai_service.news.get_headlines", return_value=fake):
        ctx = ai_service.build_market_context(db_session, "USD", "TND", date(2024, 1, 9))
    prompt = ai_service.build_prompt(ctx)
    assert "Dinar steady (TAP)" in prompt
    assert "Pair: USD/TND" in prompt


def test_commentary_endpoint_returns_headlines(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)
    fake = [models.NewsItem(pair_tag="TND", headline="Dinar steady", source="TAP",
                            url="http://x/1", fetched_date=date(2024, 1, 9))]
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.return_value.choices[0].message.content = "Commentary body text here."
    with patch("app.services.ai_service.Groq", return_value=mock_groq), \
         patch("app.services.ai_service.news.get_headlines", return_value=fake):
        resp = client.post("/api/v1/ai/commentary", json={
            "base": "USD", "quote": "TND", "date": "2024-01-09"
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["headlines"][0]["headline"] == "Dinar steady"
    assert body["headlines"][0]["source"] == "TAP"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Backend && python -m pytest tests/test_ai.py -v`
Expected: FAIL (`build_market_context`/`build_prompt` undefined; `headlines` key missing).

- [ ] **Step 3: Rewrite `ai_service.py`**

Replace the entire contents of `Backend/app/services/ai_service.py` with:

```python
from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy.orm import Session
from groq import Groq
from app import models
from app.services import analytics, alert_engine, news
from app.config import settings


@dataclass
class MarketContext:
    pair: str
    date: date
    change_pct: float
    risk_level: str
    spike: bool
    rate_history: list[str]
    trend_direction: str | None
    vol_regime: str | None
    momentum: float | None
    headlines: list  # list[models.NewsItem]


def build_market_context(db: Session, base: str, quote: str, target_date: date) -> MarketContext:
    """Assemble everything the AI needs. The only I/O is the cached news fetch."""
    # 120 days back covers the 30-day trend MA and the ~111 rows vol-regime needs.
    from_date = target_date - timedelta(days=120)
    df = analytics.load_rates_df(db, base, quote, from_date, target_date)
    if len(df) < 2:
        raise ValueError("Not enough data to generate commentary")

    change_pct = analytics.calc_daily_change(df)["change_pct"]
    spike = analytics.is_spike(df)
    risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike, quote=quote)

    trend_info = analytics.calc_trend(df)
    rate_history = [f"{r['date'].date()}: {r['rate']:.4f}" for _, r in df.tail(7).iterrows()]

    tag = news.pair_to_tag(base, quote)
    headlines = news.get_headlines(db, tag, target_date)

    return MarketContext(
        pair=f"{base}/{quote}",
        date=target_date,
        change_pct=change_pct,
        risk_level=risk_level,
        spike=spike,
        rate_history=rate_history,
        trend_direction=trend_info["direction"] if trend_info else None,
        vol_regime=analytics.calc_vol_regime(df),
        momentum=analytics.calc_momentum(df),
        headlines=headlines,
    )


def build_prompt(ctx: MarketContext) -> str:
    lines = [
        "You are a concise FX analyst.",
        f"Pair: {ctx.pair}",
        f"Date: {ctx.date}",
        f"Daily move: {ctx.change_pct:+.2f}%",
        f"Risk level: {ctx.risk_level.upper()}",
        f"7-day rate history: {', '.join(ctx.rate_history)}",
    ]
    if ctx.trend_direction:
        lines.append(f"Trend (MA7 vs MA30): {ctx.trend_direction}")
    if ctx.vol_regime:
        lines.append(f"Volatility regime: {ctx.vol_regime}")
    if ctx.momentum is not None:
        lines.append(f"Momentum: {ctx.momentum:+.2f}")
    if ctx.headlines:
        lines.append("Recent headlines:")
        for h in ctx.headlines:
            lines.append(f"  - {h.headline} ({h.source})")
    lines.append(
        "In 3-4 sentences, explain what likely drove this movement (use the headlines "
        "if relevant), what the trend and volatility context imply, and what this means "
        f"for a business with {ctx.pair} exposure (importer or exporter)."
    )
    return "\n".join(lines)


def get_or_generate_commentary(
    db: Session, base: str, quote: str, target_date: date
) -> tuple[str, bool, list]:
    """Returns (commentary_text, is_cached, headlines)."""
    existing = db.query(models.AiCommentary).filter_by(
        base_currency=base, quote_currency=quote, date=target_date
    ).first()
    if existing:
        return existing.commentary, True, []

    ctx = build_market_context(db, base, quote, target_date)
    prompt = build_prompt(ctx)

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.3,
    )
    commentary = response.choices[0].message.content.strip()

    try:
        db.add(models.AiCommentary(
            base_currency=base,
            quote_currency=quote,
            date=target_date,
            commentary=commentary,
        ))
        db.commit()
    except Exception:
        db.rollback()
        existing = db.query(models.AiCommentary).filter_by(
            base_currency=base, quote_currency=quote, date=target_date
        ).first()
        if existing:
            return existing.commentary, True, []

    return commentary, False, ctx.headlines
```

- [ ] **Step 4: Add schemas**

In `Backend/app/schemas.py`, add `HeadlineOut` and extend `CommentaryOut`:

```python
class HeadlineOut(BaseModel):
    headline: str
    source: str
    url: str
    model_config = _ORM_CONFIG


class CommentaryOut(BaseModel):
    commentary: str
    date: date
    cached: bool
    headlines: list[HeadlineOut] = []
    model_config = _ORM_CONFIG
```

(Replace the existing `CommentaryOut`; keep `CommentaryRequest` unchanged.)

- [ ] **Step 5: Update the router**

In `Backend/app/routers/ai.py`, replace the body of `get_commentary` after `_validate_pair(base, quote)`:

```python
    try:
        commentary, cached, headlines = ai_service.get_or_generate_commentary(db, base, quote, body.date)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(502, "AI commentary unavailable")
    return schemas.CommentaryOut(
        commentary=commentary,
        date=body.date,
        cached=cached,
        headlines=[schemas.HeadlineOut(headline=h.headline, source=h.source, url=h.url) for h in headlines],
    )
```

- [ ] **Step 6: Run the full backend suite**

Run: `cd Backend && python -m pytest -v`
Expected: PASS (all tests, including the pre-existing `test_ai.py` cached/502 tests — the 3-tuple return is handled).

- [ ] **Step 7: Commit**

```bash
git add Backend/app/services/ai_service.py Backend/app/schemas.py Backend/app/routers/ai.py Backend/tests/test_ai.py
git commit -m "feat: MarketContext-driven prompt with news + quote-aware risk

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Frontend data layer

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useCommentary.ts`

- [ ] **Step 1: Extend the snapshot types and mapping**

In `frontend/src/api/client.ts`, in the `Snapshot` interface add three fields after `volatility`:

```typescript
  trend: string | null;
  vol_regime: string | null;
  momentum: number | null;
```

In the `PairAnalysis` interface add after `volatility`:

```typescript
  trend: string | null;
  volRegime: string | null;
  momentum: number | null;
```

In `fetchPairAnalysis`, add to the returned object (after the `volatility:` line):

```typescript
    trend: s.trend,
    volRegime: s.vol_regime,
    momentum: s.momentum,
```

- [ ] **Step 2: Make `fetchCommentary` return headlines**

In `frontend/src/api/client.ts`, extend the `Commentary` interface:

```typescript
interface Commentary { commentary: string; date: string; cached: boolean; headlines: Headline[]; }
export interface Headline { headline: string; source: string; url: string; }
export interface CommentaryResult { commentary: string; headlines: Headline[]; }
```

Replace `fetchCommentary` with:

```typescript
/** AI market commentary for the pair, plus the headlines that informed it. */
export async function fetchCommentary(pair: string): Promise<CommentaryResult> {
  if (USE_MOCKS) return { commentary: fixtures.commentary(pair), headlines: [] };
  const { base, quote } = splitPair(pair);
  const r = await fetch(endpoints.commentary(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base, quote, date: isoDay(new Date()) }),
  });
  if (!r.ok) throw new Error(`POST commentary -> ${r.status}`);
  const data = (await r.json()) as Commentary;
  return { commentary: data.commentary, headlines: data.headlines ?? [] };
}
```

- [ ] **Step 3: Update the hook's inferred type usage**

`frontend/src/hooks/useCommentary.ts` needs no change to its body (it returns whatever `fetchCommentary` resolves to), but verify it compiles. No edit unless tsc complains.

- [ ] **Step 4: Verify it typechecks**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors in `MarketIntelligence.tsx` (it still treats `data` as a string) — that is fixed in Task 6. To confirm only-expected errors, you may temporarily skip; the clean pass is asserted at the end of Task 6.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/hooks/useCommentary.ts
git commit -m "feat: client types for signals + commentary headlines

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Frontend UI — signal badges + headline sources

**Files:**
- Create: `frontend/src/components/SignalBadges.tsx`
- Modify: `frontend/src/components/MarketIntelligence.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ui/ui.css`

- [ ] **Step 1: Create `SignalBadges`**

Create `frontend/src/components/SignalBadges.tsx`:

```tsx
import { usePairAnalysis } from '../hooks/usePairAnalysis';
import { type Pair } from '../lib/constants';

const TREND = {
  bullish: { glyph: '▲', label: 'Bullish', cls: 'sig-up' },
  bearish: { glyph: '▼', label: 'Bearish', cls: 'sig-down' },
  neutral: { glyph: '→', label: 'Neutral', cls: 'sig-flat' },
} as const;

const REGIME = {
  elevated: { label: 'Elevated vol', cls: 'sig-elevated' },
  normal: { label: 'Normal vol', cls: 'sig-normal' },
  compressed: { label: 'Compressed vol', cls: 'sig-compressed' },
} as const;

export function SignalBadges({ pair, asOf }: { pair: Pair; asOf?: string | null }) {
  const { data } = usePairAnalysis(pair, asOf);
  const trend = data?.trend && data.trend in TREND ? TREND[data.trend as keyof typeof TREND] : null;
  const regime = data?.volRegime && data.volRegime in REGIME ? REGIME[data.volRegime as keyof typeof REGIME] : null;

  if (!trend && !regime) return null;

  return (
    <div className="signal-badges">
      {trend && (
        <span className={`signal-pill ${trend.cls}`}>
          <span className="signal-glyph">{trend.glyph}</span> {trend.label}
        </span>
      )}
      {regime && <span className={`signal-pill ${regime.cls}`}>{regime.label}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Render headlines in `MarketIntelligence`**

Replace `frontend/src/components/MarketIntelligence.tsx` with:

```tsx
import { useCommentary } from '../hooks/useCommentary';
import { type Pair } from '../lib/constants';
import { fmtDateTime } from '../lib/format';
import { Card } from './ui';

const FALLBACK =
  'AI market commentary is temporarily unavailable. The figures above reflect the latest market data for this pair.';

export function MarketIntelligence({ pair, now }: { pair: Pair; now: Date }) {
  const { data, isLoading, isError } = useCommentary(pair);

  const text = isLoading
    ? 'Generating market intelligence…'
    : isError
      ? FALLBACK
      : (data?.commentary ?? FALLBACK);
  const headlines = data?.headlines ?? [];

  return (
    <Card className="ai-card">
      <div className="ai-spark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3 13.6 9.4 20 11 13.6 12.6 12 19 10.4 12.6 4 11 10.4 9.4 12 3z" />
          <path d="M19 3l.6 2.4L22 6l-2.4.6L19 9l-.6-2.4L16 6l2.4-.6L19 3z" />
        </svg>
      </div>
      <div className="ai-body">
        <div className="ai-title-row">
          <h3>Market Intelligence</h3>
          <span className="ai-tag">AI · Beta</span>
        </div>
        <p className="ai-text">{text}</p>
        {headlines.length > 0 && (
          <div className="ai-sources">
            <span className="ai-sources-label">Sources</span>
            <ul>
              {headlines.map((h) => (
                <li key={h.url}>
                  <a href={h.url} target="_blank" rel="noreferrer">{h.headline}</a>
                  <span className="ai-source-name">{h.source}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="ai-foot">
          Generated by Colombus Capital AI Engine · model.fx-r1 · <span className="mono">{fmtDateTime(now)}</span>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Render `SignalBadges` in `App.tsx`**

In `frontend/src/App.tsx`, add the import near the other component imports:

```tsx
import { SignalBadges } from './components/SignalBadges';
```

Then render it directly below the `<RiskBadge ... />` element (which is threaded with `asOf`). Use the same `pair` and `asOf` props already passed to `RiskBadge`:

```tsx
        <RiskBadge pair={pair} asOf={asOf} />
        <SignalBadges pair={pair} asOf={asOf} />
```

(If `RiskBadge` is wrapped in a container, place `<SignalBadges>` immediately after it inside the same container.)

- [ ] **Step 4: Add styles**

In `frontend/src/components/ui/ui.css`, append:

```css
/* Signal badges (trend + volatility regime) */
.signal-badges { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.signal-pill {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11.5px; font-weight: 600; letter-spacing: 0.03em;
  padding: 4px 10px; border-radius: 999px;
  background: var(--surface); border: 1px solid var(--border); color: var(--text-mute);
}
.signal-glyph { font-size: 12px; line-height: 1; }
.sig-up { color: #22C55E; border-color: rgba(34,197,94,0.35); }
.sig-down { color: #EF4444; border-color: rgba(239,68,68,0.35); }
.sig-flat { color: var(--text-mute); }
.sig-elevated { color: #F59E0B; border-color: rgba(245,158,11,0.35); }
.sig-normal { color: var(--text-mute); }
.sig-compressed { color: #3B82F6; border-color: rgba(59,130,246,0.35); }

/* AI commentary sources */
.ai-sources { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
.ai-sources-label {
  display: block; font-size: 10.5px; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--text-dim); margin-bottom: 6px;
}
.ai-sources ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.ai-sources li { font-size: 12.5px; display: flex; gap: 6px; align-items: baseline; }
.ai-sources a { color: var(--text); text-decoration: none; }
.ai-sources a:hover { color: var(--accent); text-decoration: underline; }
.ai-source-name { color: var(--text-dim); font-size: 11px; }
```

- [ ] **Step 5: Verify the frontend typechecks**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (no output).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SignalBadges.tsx frontend/src/components/MarketIntelligence.tsx frontend/src/App.tsx frontend/src/components/ui/ui.css
git commit -m "feat: trend/regime badges + AI commentary sources

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] `cd Backend && python -m pytest -v` — all green.
- [ ] `cd frontend && npx tsc --noEmit` — clean.
- [ ] Manual smoke (optional): run backend + `npm run dev`, confirm the trend arrow / regime pill appear and the Market Intelligence card lists sources for a live pair; switch the calendar date and confirm the badges follow the date while the AI card stays live.

---

## Self-Review notes

- **Spec coverage:** news service + NewsItem (T1) ✓; trend/regime/momentum (T2) ✓; snapshot+schema (T3) ✓; MarketContext/prompt/quote-aware risk/headlines-in-commentary (T4) ✓; client types (T5) ✓; badges + sources UI (T6) ✓. Out-of-scope items (scheduler, FetchLog, correlation, alert-density) intentionally absent.
- **Type consistency:** `pair_to_tag`, `get_headlines`, `calc_trend`/`calc_vol_regime`/`calc_momentum`, `build_market_context`/`build_prompt`, `MarketContext`, `SnapshotOut` fields (`trend`/`vol_regime`/`momentum`), `CommentaryResult`/`Headline`, `SignalBadges` props — names match across tasks.
- **3-tuple return:** `get_or_generate_commentary` now returns `(text, cached, headlines)`; the only caller (`routers/ai.py`) is updated in T4; pre-existing `test_ai.py` cached/502 tests still pass because they assert on the HTTP response, not the tuple.
