from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

_ORM_CONFIG = {"from_attributes": True}


class NewsArticleOut(BaseModel):
    headline: str
    source: str
    url: str
    published_at: Optional[datetime] = None
    explanation: Optional[str] = None  # Groq "why it moved" paragraph (top items only)
    model_config = _ORM_CONFIG


class NewsResponse(BaseModel):
    base: str
    quote: str
    date: date
    top: list[NewsArticleOut]   # enriched with explanations
    more: list[NewsArticleOut]  # plain headline links


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


class SnapshotOut(BaseModel):
    resolved_date: date
    rate: float
    d1: Optional[float]
    d7: Optional[float]
    d30: Optional[float]
    high: float
    low: float
    volatility: Optional[float]
    trend: Optional[str]
    vol_regime: Optional[str]
    momentum: Optional[float]
    risk: str
    model_config = _ORM_CONFIG


class CommentaryRequest(BaseModel):
    base: str
    quote: str
    date: date


class HeadlineOut(BaseModel):
    headline: str
    source: str
    url: str
    model_config = _ORM_CONFIG


class CommentaryOut(BaseModel):
    commentary: str
    date: date
    cached: bool
    headlines: list[HeadlineOut] = []
    model_config = _ORM_CONFIG


class ForwardRateOut(BaseModel):
    tenor: str
    rate: float
    pct_diff: float
    model_config = _ORM_CONFIG


class HedgeRecommendationOut(BaseModel):
    signal: str
    short_reason: str
    narrative: str
    exposure: str
    as_of: date
    spot_rate: float
    change_30d: float
    volatility: float
    risk_level: str
    forward_rates: list[ForwardRateOut] = []
    model_config = _ORM_CONFIG
