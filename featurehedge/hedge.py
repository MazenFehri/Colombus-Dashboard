from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app import schemas
from app.services import hedge_service
from app.routers.rates import _validate_pair, _ensure_rates_cached

router = APIRouter(prefix="/hedge", tags=["hedge"])


@router.get("/{base}/{quote}/recommendation", response_model=schemas.HedgeRecommendationOut)
def get_hedge_recommendation(
    base: str,
    quote: str,
    exposure: str = Query(..., pattern="^(importer|exporter)$",
                          description="Business exposure direction"),
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    """
    Returns a spot-vs-forward heuristic signal (A) plus an AI narrative (C)
    for the given currency pair and exposure direction.

    This is educational guidance — not a forward price quote.
    """
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)

    from datetime import timedelta
    _ensure_rates_cached(db, base, quote, as_of - timedelta(days=400), as_of)

    try:
        result = hedge_service.get_hedge_recommendation(db, base, quote, exposure, as_of)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Hedge recommendation unavailable: {e}")

    return schemas.HedgeRecommendationOut(**result)