from pydantic import BaseModel
from datetime import date
from typing import Optional

_ORM_CONFIG = {"from_attributes": True}


class CurrencyOut(BaseModel):
    code: str
    name: str
    model_config = _ORM_CONFIG


class RatePoint(BaseModel):
    date: date
    rate: float
    model_config = _ORM_CONFIG


class DailyChangeOut(BaseModel):
    date: date
    rate: float
    prev_rate: float
    change_pct: float
    model_config = _ORM_CONFIG


class PerformanceOut(BaseModel):
    period: str
    start_date: date
    end_date: date
    start_rate: float
    end_rate: float
    change_pct: float
    model_config = _ORM_CONFIG


class HighLowOut(BaseModel):
    high: float
    high_date: date
    low: float
    low_date: date
    model_config = _ORM_CONFIG


class VolatilityOut(BaseModel):
    rolling_21d_std: float
    annualized_vol: float
    latest_date: date
    model_config = _ORM_CONFIG


class AlertOut(BaseModel):
    date: date
    risk_level: str
    change_pct: float
    message: str
    model_config = _ORM_CONFIG


class PairSummary(BaseModel):
    pair: str
    daily_change_pct: float
    volatility: Optional[float]
    risk_level: str
    model_config = _ORM_CONFIG


class AnalysisSummaryOut(BaseModel):
    most_volatile: str
    most_stable: str
    biggest_mover: str
    pairs: list[PairSummary]
    model_config = _ORM_CONFIG


class CommentaryRequest(BaseModel):
    base: str
    quote: str
    date: date


class CommentaryOut(BaseModel):
    commentary: str
    date: date
    cached: bool
    model_config = _ORM_CONFIG
