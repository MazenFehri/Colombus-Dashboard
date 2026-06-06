import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models

_DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "USDTNDEURTND.csv")


def _seed_from_file(db: Session, csv_path: str) -> tuple[int, int, int]:
    """Parse CSV and upsert USD/TND and EUR/TND rows. Returns (inserted, updated, skipped)."""
    df = pd.read_csv(csv_path, usecols=[0, 1, 2], header=0)
    df.columns = ["date_str", "eur_usd", "usd_tnd"]
    df = df.dropna(subset=["date_str"])

    inserted = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            d = datetime.strptime(str(row["date_str"]).strip(), "%d/%m/%Y").date()
            usd_tnd = float(row["usd_tnd"])
            eur_usd = float(row["eur_usd"])
            eur_tnd = round(eur_usd * usd_tnd, 6)
        except (ValueError, TypeError):
            skipped += 1
            continue

        for base, quote, rate in [("USD", "TND", usd_tnd), ("EUR", "TND", eur_tnd)]:
            existing = db.query(models.ExchangeRate).filter_by(
                base_currency=base, quote_currency=quote, date=d
            ).first()
            if existing:
                existing.rate = rate
                existing.source = "csv"
                updated += 1
            else:
                db.add(models.ExchangeRate(
                    base_currency=base, quote_currency=quote,
                    rate=rate, date=d, source="csv"
                ))
                inserted += 1

    db.commit()
    return inserted, updated, skipped


if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    csv_path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_CSV
    db = SessionLocal()
    try:
        inserted, updated, skipped = _seed_from_file(db, csv_path)
        print(f"Done: {inserted} inserted, {updated} updated, {skipped} skipped.")
    finally:
        db.close()
