import httpx
from datetime import date, datetime
from app.config import settings
from app.services.news_config import PAIR_QUERIES, MAX_ARTICLES, LANG_CODES
from app.services.news_providers.base import Article

GNEWS_URL = "https://gnews.io/api/v4/search"


def _parse_published(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


class GNewsProvider:
    """Fallback news source (keyword + date-range search). Free-tier needs an API
    key in GNEWS_API_KEY; without one this provider no-ops so the chain degrades
    to GDELT-only. Used when GDELT returns nothing (older dates / rate-limited)."""

    name = "gnews"

    def fetch(self, base: str, quote: str, on_date: date) -> list[Article]:
        key = settings.gnews_api_key
        if not key:
            return []  # no key configured -> behave as GDELT-only
        cfg = PAIR_QUERIES[(base, quote)]
        query = " OR ".join(f'"{k}"' for k in cfg["keywords"])
        langs = ",".join(LANG_CODES.get(l, l) for l in cfg["languages"])
        params = {
            "q": query,
            "apikey": key,
            "max": MAX_ARTICLES,
            "lang": langs,
            "sortby": "relevance",
            "from": f"{on_date.isoformat()}T00:00:00Z",
            "to": f"{on_date.isoformat()}T23:59:59Z",
        }
        resp = httpx.get(GNEWS_URL, params=params, timeout=15)
        if resp.status_code in (401, 403, 429):
            return []  # auth / quota issues -> degrade gracefully
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
                source=(a.get("source") or {}).get("name", ""),
                published_at=_parse_published(a.get("publishedAt", "")),
                language="",
                relevance=1.0 - i / MAX_ARTICLES,
            ))
        return articles
