from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app import models, schemas
from app.services import frankfurter, analytics

router = APIRouter(prefix="/rates", tags=["rates"])

SUPPORTED_PAIRS = {("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")}


def _validate_pair(base: str, quote: str):
    if (base, quote) not in SUPPORTED_PAIRS:
        raise HTTPException(400, f"Unsupported currency pair: {base}/{quote}. "
                                 f"Supported: EUR/USD, GBP/USD, USD/TND, EUR/TND")


def _ensure_rates_cached(db: Session, base: str, quote: str, from_date: date, to_date: date):
    """Fetch from appropriate source only if we don't have enough data in DB for the range."""
    total_days = (to_date - from_date).days + 1
    count = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.base_currency == base,
        models.ExchangeRate.quote_currency == quote,
        models.ExchangeRate.date >= from_date,
        models.ExchangeRate.date <= to_date,
    ).count()
    expected_min = max(1, int(total_days * 5 / 7 * 0.8))
    if count >= expected_min:
        return

    try:
        new_rates = frankfurter.fetch_rates(base, quote, from_date, to_date)
        source = "frankfurter"
    except RuntimeError as e:
        if count == 0:
            raise HTTPException(503, str(e))
        return  # serve whatever partial cache exists
    for rate_date, rate_val in new_rates.items():
        existing = db.query(models.ExchangeRate).filter_by(
            base_currency=base, quote_currency=quote, date=rate_date
        ).first()
        if existing:
            existing.rate = rate_val
        else:
            db.add(models.ExchangeRate(
                base_currency=base, quote_currency=quote,
                rate=rate_val, date=rate_date, source=source
            ))
    db.commit()


@router.get("/{base}/{quote}", response_model=list[schemas.RatePoint])
def get_historical_rates(
    base: str,
    quote: str,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    to_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    if from_date > to_date:
        raise HTTPException(400, "Invalid date range: from_date must be before to_date")
    _ensure_rates_cached(db, base, quote, from_date, to_date)
    rows = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.base_currency == base,
            models.ExchangeRate.quote_currency == quote,
            models.ExchangeRate.date >= from_date,
            models.ExchangeRate.date <= to_date,
        )
        .order_by(models.ExchangeRate.date)
        .all()
    )
    return [schemas.RatePoint(date=r.date, rate=r.rate) for r in rows]


@router.get("/{base}/{quote}/daily-change", response_model=schemas.DailyChangeOut)
def get_daily_change(
    base: str,
    quote: str,
    date_param: date = Query(alias="date", default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    from_date = date_param - timedelta(days=5)
    _ensure_rates_cached(db, base, quote, from_date, date_param)
    df = analytics.load_rates_df(db, base, quote, from_date, date_param)
    try:
        result = analytics.calc_daily_change(df)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return schemas.DailyChangeOut(**result)


@router.get("/{base}/{quote}/performance", response_model=schemas.PerformanceOut)
def get_performance(
    base: str,
    quote: str,
    period: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    days = 7 if period == "weekly" else 30
    to_date = date.today()
    from_date = to_date - timedelta(days=days + 5)
    _ensure_rates_cached(db, base, quote, from_date, to_date)
    df = analytics.load_rates_df(db, base, quote, from_date, to_date)
    try:
        result = analytics.calc_performance(df, period)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return schemas.PerformanceOut(**result)


@router.get("/{base}/{quote}/high-low", response_model=schemas.HighLowOut)
def get_high_low(
    base: str,
    quote: str,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    to_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    if from_date > to_date:
        raise HTTPException(400, "Invalid date range")
    _ensure_rates_cached(db, base, quote, from_date, to_date)
    df = analytics.load_rates_df(db, base, quote, from_date, to_date)
    try:
        result = analytics.calc_high_low(df)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return schemas.HighLowOut(**result)


@router.get("/{base}/{quote}/volatility", response_model=schemas.VolatilityOut)
def get_volatility(
    base: str,
    quote: str,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=365)),
    to_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    if from_date > to_date:
        raise HTTPException(400, "Invalid date range")
    _ensure_rates_cached(db, base, quote, from_date, to_date)
    df = analytics.load_rates_df(db, base, quote, from_date, to_date)
    try:
        result = analytics.calc_volatility(df)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return schemas.VolatilityOut(**result)
