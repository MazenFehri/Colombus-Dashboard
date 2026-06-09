import time
import httpx
from datetime import date, datetime
from app.services.news_config import PAIR_QUERIES, MAX_ARTICLES, GDELT_MIN_INTERVAL_SEC
from app.services.news_providers.base import Article

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT's free endpoint rate-limits to roughly one request every 5 seconds and
# returns HTTP 429 when exceeded. Space *live* calls process-wide to stay under it.
_last_live_call: float = 0.0


def _throttle_live() -> None:
    global _last_live_call
    wait = GDELT_MIN_INTERVAL_SEC - (time.monotonic() - _last_live_call)
    if wait > 0:
        time.sleep(wait)
    _last_live_call = time.monotonic()


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
        is_live = on_date >= date.today()
        if is_live:
            params["timespan"] = "3d"
            # Only live/recent queries trip the rate limit; historical date-range
            # queries return fast and don't, so we don't slow the nearest-day probe.
            _throttle_live()
        else:
            params["startdatetime"] = on_date.strftime("%Y%m%d000000")
            params["enddatetime"] = on_date.strftime("%Y%m%d235959")

        resp = httpx.get(GDELT_URL, params=params, timeout=15)
        # A 429 (rate-limited) is transient, not a hard failure — degrade to empty
        # so the provider chain can fall back rather than surfacing an error.
        if resp.status_code == 429:
            return []
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            # GDELT occasionally returns a plain-text notice with HTTP 200.
            return []

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
                relevance=1.0 - i / MAX_ARTICLES,
            ))
        return articles
