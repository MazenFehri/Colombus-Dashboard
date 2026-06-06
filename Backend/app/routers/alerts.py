from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app import models, schemas
from app.services import frankfurter, analytics, alert_engine
from app.routers.rates import _validate_pair, _ensure_rates_cached

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _compute_and_store_alert(db: Session, base: str, quote: str, target_date: date) -> schemas.AlertOut:
    existing = db.query(models.Alert).filter_by(
        base_currency=base, quote_currency=quote, date=target_date
    ).first()
    if existing:
        return schemas.AlertOut(
            date=existing.date,
            risk_level=existing.risk_level,
            change_pct=existing.daily_change_pct,
            message=existing.message,
        )

    from_date = target_date - timedelta(days=70)
    _ensure_rates_cached(db, base, quote, from_date, target_date)
    df = analytics.load_rates_df(db, base, quote, from_date, target_date)

    try:
        change_data = analytics.calc_daily_change(df)
    except ValueError as e:
        raise HTTPException(422, str(e))

    spike = analytics.is_spike(df)
    risk_level, message = alert_engine.classify_risk(change_data["change_pct"], spike=spike)

    alert = models.Alert(
        base_currency=base,
        quote_currency=quote,
        date=target_date,
        risk_level=risk_level,
        daily_change_pct=change_data["change_pct"],
        message=message,
    )
    db.add(alert)
    db.commit()

    return schemas.AlertOut(
        date=target_date,
        risk_level=risk_level,
        change_pct=change_data["change_pct"],
        message=message,
    )


@router.get("/{base}/{quote}", response_model=schemas.AlertOut)
def get_alert(
    base: str,
    quote: str,
    date_param: date = Query(alias="date", default_factory=date.today),
    db: Session = Depends(get_db),
):
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)
    return _compute_and_store_alert(db, base, quote, date_param)


@router.get("/{base}/{quote}/history", response_model=list[schemas.AlertOut])
def get_alert_history(
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

    _ensure_rates_cached(db, base, quote, from_date - timedelta(days=5), to_date)
    df = analytics.load_rates_df(db, base, quote, from_date - timedelta(days=5), to_date)

    results = []
    target_dates = [r["date"].date() for _, r in df[df["date"].dt.date >= from_date].iterrows()]
    for d in target_dates:
        try:
            alert = _compute_and_store_alert(db, base, quote, d)
            results.append(alert)
        except HTTPException:
            continue
    return results
