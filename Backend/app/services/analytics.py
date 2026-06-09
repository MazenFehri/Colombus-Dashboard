import pandas as pd
import numpy as np
from datetime import date
from sqlalchemy.orm import Session
from app import models
from app.services import alert_engine


def load_rates_df(db: Session, base: str, quote: str, from_date: date, to_date: date) -> pd.DataFrame:
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
    if not rows:
        return pd.DataFrame(columns=["date", "rate"])
    df = pd.DataFrame([{"date": r.date, "rate": float(r.rate)} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def calc_daily_change(df: pd.DataFrame) -> dict:
    if len(df) < 2:
        raise ValueError("Need at least 2 days of data for daily change")
    today = df.iloc[-1]
    prev = df.iloc[-2]
    change_pct = (today["rate"] - prev["rate"]) / prev["rate"] * 100
    return {
        "date": today["date"].date(),
        "rate": round(float(today["rate"]), 6),
        "prev_rate": round(float(prev["rate"]), 6),
        "change_pct": round(float(change_pct), 4),
    }


def calc_performance(df: pd.DataFrame, period: str) -> dict:
    if len(df) < 2:
        raise ValueError("Not enough data for performance calculation")
    days = 7 if period == "weekly" else 30
    end_row = df.iloc[-1]
    start_row = df.iloc[max(0, len(df) - days - 1)]
    change_pct = (end_row["rate"] - start_row["rate"]) / start_row["rate"] * 100
    return {
        "period": period,
        "start_date": start_row["date"].date(),
        "end_date": end_row["date"].date(),
        "start_rate": round(float(start_row["rate"]), 6),
        "end_rate": round(float(end_row["rate"]), 6),
        "change_pct": round(float(change_pct), 4),
    }


def calc_high_low(df: pd.DataFrame) -> dict:
    if df.empty:
        raise ValueError("No data available")
    high_idx = df["rate"].idxmax()
    low_idx = df["rate"].idxmin()
    return {
        "high": round(float(df.loc[high_idx, "rate"]), 6),
        "high_date": df.loc[high_idx, "date"].date(),
        "low": round(float(df.loc[low_idx, "rate"]), 6),
        "low_date": df.loc[low_idx, "date"].date(),
    }


def _normalized_returns(df: pd.DataFrame) -> pd.Series:
    """Daily returns normalized by actual calendar-day gaps between observations.

    Rate data has missing days (weekends, public holidays). A raw pct_change over
    a 3-day gap would be counted as a 1-day return, inflating volatility estimates.
    Dividing by sqrt(gap_days) rescales multi-day returns to a 1-day equivalent
    so the rolling std is a consistent estimator of 1-day volatility.
    """
    day_gaps = df["date"].diff().dt.days.fillna(1).clip(lower=1)
    raw = df["rate"].pct_change()
    return (raw / np.sqrt(day_gaps)).dropna()


def calc_volatility(df: pd.DataFrame) -> dict:
    if len(df) < 21:
        raise ValueError("Need at least 21 days of data for volatility")
    pct = _normalized_returns(df)
    rolling_stds = pct.rolling(21).std().dropna()
    # Use most recent non-zero rolling std — a flat tail (e.g. scraped constant values)
    # would otherwise mask real historical volatility.
    non_zero = rolling_stds[rolling_stds > 0]
    rolling_std = float(non_zero.iloc[-1]) if not non_zero.empty else 0.0
    annualized = rolling_std * np.sqrt(252)
    return {
        "rolling_21d_std": round(rolling_std, 6),
        "annualized_vol": round(float(annualized), 6),
        "latest_date": df.iloc[-1]["date"].date(),
    }


def calc_trend(df: pd.DataFrame) -> dict | None:
    """MA7 vs MA30 directional signal. None if < 30 rows."""
    if len(df) < 30:
        return None
    ma7 = float(df["rate"].tail(7).mean())
    ma30 = float(df["rate"].tail(30).mean())
    if ma30 == 0 or pd.isna(ma7) or pd.isna(ma30):
        return None
    spread = abs(ma7 - ma30) / ma30
    if spread < 0.001:
        direction = "neutral"
    elif ma7 > ma30:
        direction = "bullish"
    else:
        direction = "bearish"
    return {"direction": direction, "ma7": round(ma7, 6), "ma30": round(ma30, 6)}


def calc_vol_regime(df: pd.DataFrame) -> str | None:
    """Current 21d vol vs the 90-obs average of that rolling vol.

    elevated  > 1.5x average; compressed < 0.6x average; else normal.
    None when there are < 90 rolling-std observations or the average is 0.
    Requires at least 111 input rows (90 rolling-std observations).
    """
    pct = _normalized_returns(df)
    rolling = pct.rolling(21).std().dropna()
    if len(rolling) < 90:
        return None
    current = float(rolling.iloc[-1])
    if current == 0:
        return None
    avg = float(rolling.tail(90).mean())
    if avg == 0:
        return None
    if current > 1.5 * avg:
        return "elevated"
    if current < 0.6 * avg:
        return "compressed"
    return "normal"


def calc_momentum(df: pd.DataFrame) -> float | None:
    """Acceleration of the daily return: (today - yesterday) / |yesterday|.

    Returns None if < 3 rows or yesterday's return is ~0.
    """
    if len(df) < 3:
        return None
    pct = _normalized_returns(df) * 100
    # all-zero rates make every pct_change NaN -> dropped
    if len(pct) < 2:
        return None
    today = float(pct.iloc[-1])
    yest = float(pct.iloc[-2])
    if abs(yest) < 1e-9:
        return None
    return round((today - yest) / abs(yest), 4)


def build_snapshot(df: pd.DataFrame, as_of: date, quote: str) -> dict:
    """Compute the full per-pair analysis as of a target date.

    Pure function: takes an already-loaded rate DataFrame, resolves ``as_of`` to
    the latest available trading day at or before it (handling holidays/weekends),
    and reuses the existing metric helpers. Fields lacking enough history are
    returned as ``None``.

    Raises ``ValueError`` if no row exists at or before ``as_of``.
    """
    as_of_ts = pd.Timestamp(as_of)
    eligible = df[df["date"] <= as_of_ts]
    if eligible.empty:
        raise ValueError(f"No data available at or before {as_of}")

    sliced = eligible.reset_index(drop=True)
    resolved_date = sliced.iloc[-1]["date"].date()
    rate = round(float(sliced.iloc[-1]["rate"]), 6)

    try:
        d1 = calc_daily_change(sliced)["change_pct"]
    except ValueError:
        d1 = None

    try:
        d7 = calc_performance(sliced, "weekly")["change_pct"]
    except ValueError:
        d7 = None

    try:
        d30 = calc_performance(sliced, "monthly")["change_pct"]
    except ValueError:
        d30 = None

    # High/low over the 30 days ending at resolved_date.
    window_start = pd.Timestamp(resolved_date) - pd.Timedelta(days=30)
    window = sliced[sliced["date"] >= window_start]
    hl = calc_high_low(window if not window.empty else sliced)
    high, low = hl["high"], hl["low"]

    try:
        volatility = calc_volatility(sliced)["rolling_21d_std"]
    except ValueError:
        volatility = None

    if d1 is not None:
        risk, _ = alert_engine.classify_risk(d1, spike=is_spike(sliced), quote=quote)
    else:
        risk = "low"

    return {
        "resolved_date": resolved_date,
        "rate": rate,
        "d1": d1,
        "d7": d7,
        "d30": d30,
        "high": high,
        "low": low,
        "volatility": volatility,
        "risk": risk,
    }


def is_spike(df: pd.DataFrame) -> bool:
    if len(df) < 64:
        return False
    pct = _normalized_returns(df)
    if len(pct) < 63:
        return False
    latest = float(pct.iloc[-1])
    sigma = float(pct.rolling(63).std().dropna().iloc[-1])
    if sigma == 0:
        return False
    return abs(latest) > 3 * sigma
