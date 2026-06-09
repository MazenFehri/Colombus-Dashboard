from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app import schemas
from app.services import news_section
from app.routers.rates import _validate_pair

router = APIRouter(prefix="/news", tags=["news"])


def _out(it, explained: bool) -> schemas.NewsArticleOut:
    return schemas.NewsArticleOut(
        headline=it.headline,
        source=it.source,
        url=it.url,
        published_at=it.published_at,
        explanation=it.explanation if explained else None,
    )


@router.get("/{base}/{quote}", response_model=schemas.NewsResponse)
def get_news(
    base: str,
    quote: str,
    date_param: date = Query(alias="date", default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    # Never surface a 5xx to the UI: degrade to an empty result on any failure.
    try:
        top, more = news_section.get_pair_news(db, base, quote, date_param)
    except Exception:
        top, more = [], []
    return schemas.NewsResponse(
        base=base, quote=quote, date=date_param,
        top=[_out(i, True) for i in top],
        more=[_out(i, False) for i in more],
    )
