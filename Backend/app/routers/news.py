from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services import news_section, digest_builder, email_service
from app.services.deps import get_current_user
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


@router.post("/email", response_model=schemas.EmailNewsOut)
def email_news(
    body: schemas.EmailNewsIn,
    current: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    on_date = date.fromisoformat(body.date) if body.date else date.today()
    subject, html = digest_builder.build_digest_html(db, on_date)
    try:
        email_service.send_email(current.email, subject, html)
    except email_service.EmailError:
        raise HTTPException(status_code=502, detail="Email delivery failed")
    return schemas.EmailNewsOut(sent=True, to=current.email)
