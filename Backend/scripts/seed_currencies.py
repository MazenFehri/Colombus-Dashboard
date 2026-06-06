import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app import models

models.Base.metadata.create_all(bind=engine)

CURRENCIES = [
    {"code": "EUR", "name": "Euro"},
    {"code": "USD", "name": "US Dollar"},
    {"code": "GBP", "name": "British Pound Sterling"},
    {"code": "TND", "name": "Tunisian Dinar"},
]

db = SessionLocal()
for c in CURRENCIES:
    if not db.query(models.Currency).filter_by(code=c["code"]).first():
        db.add(models.Currency(**c))
db.commit()
db.close()
print("Currencies seeded successfully.")
