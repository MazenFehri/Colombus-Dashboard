from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(tags=["currencies"])


@router.get("/currencies", response_model=list[schemas.CurrencyOut])
def list_currencies(db: Session = Depends(get_db)):
    return db.query(models.Currency).order_by(models.Currency.code).all()
