from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine
from app import models
from app.routers import currencies, rates, alerts, analysis, ai


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
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
