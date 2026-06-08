"""One-off migration: replace CSV/scraper TND data with Frankfurter v2 rates.

Removes all exchange_rate rows sourced from the retired 'csv' and 'bct' pipelines,
re-fetches USD/TND and EUR/TND directly from Frankfurter v2, and clears the TND
alerts/commentary that were derived from the old data so they regenerate cleanly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.database import SessionLocal, engine
from app import models
from app.services import frankfurter

START = date(2020, 4, 9)          # earliest date the old TND data covered
TND_PAIRS = [("USD", "TND"), ("EUR", "TND")]


def main():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Drop retired-source rows
        deleted = (
            db.query(models.ExchangeRate)
            .filter(models.ExchangeRate.source.in_(["csv", "bct"]))
            .delete(synchronize_session=False)
        )
        print(f"Deleted {deleted} csv/bct exchange_rate rows.")

        # 2. Clear TND alerts + commentary derived from old data
        for base, quote in TND_PAIRS:
            a = db.query(models.Alert).filter_by(base_currency=base, quote_currency=quote).delete(synchronize_session=False)
            c = db.query(models.AiCommentary).filter_by(base_currency=base, quote_currency=quote).delete(synchronize_session=False)
            print(f"Cleared {a} alerts, {c} commentary for {base}/{quote}.")

        db.commit()

        # 3. Re-fetch from Frankfurter v2 and insert
        today = date.today()
        for base, quote in TND_PAIRS:
            rates = frankfurter.fetch_rates(base, quote, START, today)
            for d, r in sorted(rates.items()):
                db.add(models.ExchangeRate(
                    base_currency=base, quote_currency=quote,
                    rate=r, date=d, source="frankfurter",
                ))
            print(f"Inserted {len(rates)} {base}/{quote} rows from Frankfurter "
                  f"({min(rates)} .. {max(rates)}).")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
