from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.routers.rates import _ensure_rates_cached, _validate_pair
from app.services import hedge_service

router = APIRouter(prefix="/hedge", tags=["hedge"])


@router.get("/{base}/{quote}/recommendation", response_model=schemas.HedgeRecommendationOut)
def get_hedge_recommendation(
    base: str,
    quote: str,
    exposure: str = Query(..., pattern="^(importer|exporter)$"),
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    """Spot-vs-forward guidance: heuristic signal (A) + CIP forward rates (B) + AI narrative (C)."""
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    _ensure_rates_cached(db, base, quote, as_of - timedelta(days=400), as_of)

    try:
        result = hedge_service.get_hedge_recommendation(db, base, quote, exposure, as_of)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Hedge recommendation unavailable: {e}")

    return schemas.HedgeRecommendationOut(**result)
