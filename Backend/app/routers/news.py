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
