import pandas as pd
import numpy as np
from datetime import date
from sqlalchemy.orm import Session
from app import models


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


def calc_volatility(df: pd.DataFrame) -> dict:
    if len(df) < 21:
        raise ValueError("Need at least 21 days of data for volatility")
    pct = df["rate"].pct_change().dropna()
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


def is_spike(df: pd.DataFrame) -> bool:
    if len(df) < 64:
        return False
    pct = df["rate"].pct_change().dropna()
    latest = float(pct.iloc[-1])
    sigma = float(pct.rolling(63).std().dropna().iloc[-1])
    return abs(latest) > 3 * sigma
