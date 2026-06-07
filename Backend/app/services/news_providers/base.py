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
