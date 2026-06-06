import os
import sys
import tempfile
import pytest
from datetime import date
from app import models

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAMPLE_CSV = """Date,EUR/TND,USD/TND ,,
9/4/2020,1.0927,2.9064,,
10/4/2020,1.0935,2.9064,,
bad_row,notanumber,2.9064,,
"""


def _write_tmp_csv(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w") as f:
        f.write(content)
    return path


def test_seed_inserts_usd_and_eur_tnd_rows(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        usd_rows = db_session.query(models.ExchangeRate).filter_by(
            base_currency="USD", quote_currency="TND"
        ).all()
        eur_rows = db_session.query(models.ExchangeRate).filter_by(
            base_currency="EUR", quote_currency="TND"
        ).all()
        assert len(usd_rows) == 2
        assert len(eur_rows) == 2
    finally:
        os.unlink(path)


def test_seed_derives_eur_tnd_correctly(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        eur_row = db_session.query(models.ExchangeRate).filter_by(
            base_currency="EUR", quote_currency="TND", date=date(2020, 4, 9)
        ).first()
        # EUR/TND = 1.0927 (EUR/USD col) × 2.9064 (USD/TND col)
        assert eur_row is not None
        assert abs(eur_row.rate - (1.0927 * 2.9064)) < 0.0001
    finally:
        os.unlink(path)


def test_seed_stores_usd_tnd_directly(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        usd_row = db_session.query(models.ExchangeRate).filter_by(
            base_currency="USD", quote_currency="TND", date=date(2020, 4, 9)
        ).first()
        assert usd_row is not None
        assert abs(usd_row.rate - 2.9064) < 0.0001
    finally:
        os.unlink(path)


def test_seed_skips_unparseable_rows(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        # Only 2 valid rows; bad_row is skipped
        count = db_session.query(models.ExchangeRate).filter_by(
            base_currency="USD", quote_currency="TND"
        ).count()
        assert count == 2
    finally:
        os.unlink(path)


def test_seed_is_idempotent(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        _seed_from_file(db_session, path)
        count = db_session.query(models.ExchangeRate).filter_by(
            base_currency="USD", quote_currency="TND"
        ).count()
        assert count == 2  # no duplicates on second run
    finally:
        os.unlink(path)


def test_seed_sets_source_to_csv(db_session):
    from scripts.seed_tnd_rates import _seed_from_file
    path = _write_tmp_csv(SAMPLE_CSV)
    try:
        _seed_from_file(db_session, path)
        row = db_session.query(models.ExchangeRate).filter_by(
            base_currency="USD", quote_currency="TND"
        ).first()
        assert row.source == "csv"
    finally:
        os.unlink(path)
