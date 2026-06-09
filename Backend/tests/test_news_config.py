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
