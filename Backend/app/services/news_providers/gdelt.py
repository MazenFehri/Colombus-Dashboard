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
                relevance=1.0 - i / MAX_ARTICLES,
            ))
        return articles
