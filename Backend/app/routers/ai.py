from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.services import ai_service, news_service
from app.routers.rates import _validate_pair

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/commentary", response_model=schemas.CommentaryOut)
def get_commentary(
    body: schemas.CommentaryRequest,
    db: Session = Depends(get_db),
):
    base, quote = body.base.upper(), body.quote.upper()
    _validate_pair(base, quote)
    try:
        articles = news_service.get_or_fetch_news(db, base, quote, body.date)
        headlines = [a.title for a in articles if getattr(a, "is_top", False)]
    except Exception:
        headlines = []
    try:
        commentary, cached = ai_service.get_or_generate_commentary(
            db, base, quote, body.date, headlines=headlines
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(502, "AI commentary unavailable")
    return schemas.CommentaryOut(commentary=commentary, date=body.date, cached=cached)
