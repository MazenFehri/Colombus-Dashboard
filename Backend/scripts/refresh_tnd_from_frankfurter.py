"""Rebuild exchange_rates with continuous Frankfurter v2 history for all 4 pairs.

Deletes every exchange_rate row (including the retired 'csv'/'bct' data and any
short-range 'frankfurter' rows) and re-fetches all four pairs from a single START
date so the dashboard has aligned, gap-free history. Also clears alerts/commentary
so they regenerate from the fresh data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.database import SessionLocal, engine
from app import models
from app.services import frankfurter

START = date(2020, 4, 9)          # common start so all 4 pairs share one range
ALL_PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")]


def main():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Wipe all rate rows and cached derivations, then confirm empty
        deleted = db.query(models.ExchangeRate).delete(synchronize_session=False)
        a = db.query(models.Alert).delete(synchronize_session=False)
        c = db.query(models.AiCommentary).delete(synchronize_session=False)
        db.commit()
        remaining = db.query(models.ExchangeRate).count()
        print(f"Deleted {deleted} exchange_rate rows, {a} alerts, {c} commentary. "
              f"Remaining: {remaining}.")
        if remaining:
            raise RuntimeError(f"exchange_rates not empty after delete ({remaining} rows)")

        # 2. Fetch every pair from one START date, dedupe defensively, insert
        today = date.today()
        for base, quote in ALL_PAIRS:
            rates = frankfurter.fetch_rates(base, quote, START, today)
            rows = {d: r for d, r in rates.items() if d >= START}  # drop any leading anchor
            for d, r in sorted(rows.items()):
                db.add(models.ExchangeRate(
                    base_currency=base, quote_currency=quote,
                    rate=r, date=d, source="frankfurter",
                ))
            db.commit()  # commit per pair so a failure is isolated and diagnosable
            print(f"Inserted {len(rows)} {base}/{quote} rows from Frankfurter "
                  f"({min(rows)} .. {max(rows)}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
