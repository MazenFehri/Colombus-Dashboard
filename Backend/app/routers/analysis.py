from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app import schemas
from app.services import analytics, alert_engine
from app.routers.rates import _ensure_rates_cached, _validate_pair, SUPPORTED_PAIRS

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/summary", response_model=schemas.AnalysisSummaryOut)
def get_analysis_summary(db: Session = Depends(get_db)):
    to_date = date.today()
    from_date = to_date - timedelta(days=60)

    pair_summaries = []
    for base, quote in SUPPORTED_PAIRS:
        try:
            _ensure_rates_cached(db, base, quote, from_date, to_date)
            df = analytics.load_rates_df(db, base, quote, from_date, to_date)
            if len(df) < 2:
                continue

            change_data = analytics.calc_daily_change(df)
            change_pct = change_data["change_pct"]

            vol_data = None
            if len(df) >= 21:
                vol_data = analytics.calc_volatility(df)

            spike = analytics.is_spike(df)
            risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike, quote=quote)

            pair_summaries.append(schemas.PairSummary(
                pair=f"{base}/{quote}",
                daily_change_pct=change_pct,
                volatility=vol_data["annualized_vol"] if vol_data else None,
                risk_level=risk_level,
            ))
        except Exception:
            continue

    if not pair_summaries:
        return schemas.AnalysisSummaryOut(
            most_volatile="N/A", most_stable="N/A", biggest_mover="N/A", pairs=[]
        )

    pairs_with_vol = [p for p in pair_summaries if p.volatility is not None]
    most_volatile = max(pairs_with_vol, key=lambda p: p.volatility).pair if pairs_with_vol else "N/A"
    most_stable = min(pairs_with_vol, key=lambda p: p.volatility).pair if pairs_with_vol else "N/A"
    biggest_mover = max(pair_summaries, key=lambda p: abs(p.daily_change_pct)).pair

    return schemas.AnalysisSummaryOut(
        most_volatile=most_volatile,
        most_stable=most_stable,
        biggest_mover=biggest_mover,
        pairs=pair_summaries,
    )


@router.get("/{base}/{quote}/snapshot", response_model=schemas.SnapshotOut)
def get_snapshot(
    base: str,
    quote: str,
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    """Full per-pair analysis as of a given date (defaults to today/live).

    Resolves ``as_of`` to the nearest prior trading day server-side, so holidays
    and weekends fall back gracefully.
    """
    base, quote = base.upper(), quote.upper()
    _validate_pair(base, quote)

    # ~400 calendar days of history ending at as_of covers the 30-day window and
    # the rolling-21d volatility math with comfortable margin.
    from_date = as_of - timedelta(days=400)
    _ensure_rates_cached(db, base, quote, from_date, as_of)
    df = analytics.load_rates_df(db, base, quote, from_date, as_of)

    try:
        snap = analytics.build_snapshot(df, as_of, quote)
    except ValueError as e:
        raise HTTPException(422, str(e))

    snap["risk"] = snap["risk"].upper()
    return schemas.SnapshotOut(**snap)
