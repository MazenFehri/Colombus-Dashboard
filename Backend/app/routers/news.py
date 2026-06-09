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
    # Never surface a 500 to the UI: on any failure degrade to an empty result
    # so the News card shows "no news for this date" rather than an error.
    try:
        articles, effective = news_service.get_news_nearest(db, base, quote, date_param)
    except Exception:
        articles, effective = [], date_param
    top = [a for a in articles if a.is_top]
    more = [a for a in articles if not a.is_top]
    return schemas.NewsResponse(
        base=base, quote=quote, date=date_param,
        effective_date=effective, top=top, more=more,
    )
