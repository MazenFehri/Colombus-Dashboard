from sqlalchemy import Column, Integer, Text, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class Currency(Base):
    __tablename__ = "currencies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    base_currency = Column(Text, nullable=False)
    quote_currency = Column(Text, nullable=False)
    rate = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    source = Column(Text, nullable=False, default="frankfurter")
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "date"),)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    base_currency = Column(Text, nullable=False)
    quote_currency = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    risk_level = Column(Text, nullable=False)
    daily_change_pct = Column(Float, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "date"),)


class AiCommentary(Base):
    __tablename__ = "ai_commentary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    base_currency = Column(Text, nullable=False)
    quote_currency = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    commentary = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", "date"),)
