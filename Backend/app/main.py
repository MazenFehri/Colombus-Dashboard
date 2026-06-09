from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.database import engine
from app import models
from app.routers import currencies, rates, alerts, analysis, ai, news


def _heal_schema() -> None:
    """create_all() never ALTERs existing tables, so a column added to a model
    after its table already existed is missing on older databases. Add it here so
    a stale DB self-heals instead of raising 'no such column'."""
    insp = inspect(engine)
    if "news_items" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("news_items")}
        if "explanation" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE news_items ADD COLUMN explanation TEXT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    _heal_schema()
    yield


app = FastAPI(title="FX Risk Alert Dashboard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(currencies.router, prefix="/api/v1")
app.include_router(rates.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(news.router, prefix="/api/v1")
