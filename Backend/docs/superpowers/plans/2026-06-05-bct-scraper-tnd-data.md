# BCT Scraper & TND Historical Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken fawazahmed fallback for TND pairs with a real BCT scraper and seed 6 years of historical USD/TND and EUR/TND data from CSV, giving the AI layer a solid historical baseline for risk interpretation.

**Architecture:** EUR/USD and GBP/USD continue to use Frankfurter v2. USD/TND and EUR/TND are routed to a new `bct.py` service that scrapes `cours.jsp` per date using `pd.read_html`. A one-time seed script reads `USDTNDEURTND.csv`, derives `EUR/TND = EUR/USD_col × USD/TND_col`, and upserts into `exchange_rates`. The BCT scraper then fills any gap between the CSV end date and today on first request; all results are cached in the DB.

**Tech Stack:** FastAPI, SQLAlchemy, pandas (`pd.read_html`), httpx, lxml (new), pytest, SQLite

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `lxml>=5.0` |
| `app/services/bct.py` | Create | BCT HTML scraper — `fetch_rates`, `_fetch_single_date` |
| `tests/test_bct.py` | Create | Unit tests for BCT scraper |
| `app/routers/rates.py` | Modify | Route TND pairs to `bct.fetch_rates`, others to `frankfurter.fetch_rates` |
| `tests/test_rates.py` | Modify | Update mock target for TND-pair cache test |
| `scripts/seed_tnd_rates.py` | Create | CSV import — parses CSV, derives EUR/TND, upserts to DB |
| `tests/test_seed_tnd_rates.py` | Create | Unit tests for seed logic |

---

## Task 1: Add lxml dependency

**Files:**
- Modify: `Backend/requirements.txt`

- [ ] **Step 1: Add lxml to requirements.txt**

Open `Backend/requirements.txt` and add this line after `numpy`:

```
lxml>=5.0
```

Full file after edit:
```
fastapi>=0.111
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pydantic-settings>=2.0
httpx>=0.27
pandas>=2.0
numpy>=1.26
lxml>=5.0
python-dotenv>=1.0
groq>=0.9
pytest>=8.0
pytest-mock>=3.14
```

- [ ] **Step 2: Install it**

Run from `Backend/`:
```
pip install lxml>=5.0
```

Expected: installs without error. Verify:
```
python -c "import lxml; print(lxml.__version__)"
```

- [ ] **Step 3: Commit**

```bash
git add Backend/requirements.txt
git commit -m "chore: add lxml for pd.read_html HTML parsing"
```

---

## Task 2: BCT scraper service (TDD)

**Files:**
- Create: `Backend/tests/test_bct.py`
- Create: `Backend/app/services/bct.py`

- [ ] **Step 1: Write failing tests**

Create `Backend/tests/test_bct.py`:

```python
from unittest.mock import patch, MagicMock
from datetime import date
from app.services import bct

MOCK_HTML = """
<html><body>
<table>
  <tr><th>Monnaie</th><th>Sigle</th><th>Unite</th><th>Valeur</th></tr>
  <tr><td>Dollar Americain</td><td>USD</td><td>1</td><td>2,9131</td></tr>
  <tr><td>Euro</td><td>EUR</td><td>1</td><td>3,3865</td></tr>
</table>
</body></html>
"""


def _mock_response(status_code=200, html=MOCK_HTML):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = html
    return mock_resp


def test_fetch_single_date_usd():
    with patch("httpx.get", return_value=_mock_response()):
        result = bct._fetch_single_date("USD", date(2026, 6, 3))
    assert result == 2.9131


def test_fetch_single_date_eur():
    with patch("httpx.get", return_value=_mock_response()):
        result = bct._fetch_single_date("EUR", date(2026, 6, 3))
    assert result == 3.3865


def test_fetch_single_date_returns_none_on_404():
    with patch("httpx.get", return_value=_mock_response(status_code=404)):
        result = bct._fetch_single_date("USD", date(2026, 6, 1))
    assert result is None


def test_fetch_single_date_returns_none_on_exception():
    with patch("httpx.get", side_effect=Exception("network error")):
        result = bct._fetch_single_date("USD", date(2026, 6, 1))
    assert result is None


def test_fetch_rates_skips_weekends():
    # Mon 2026-06-01 through Sun 2026-06-07 → only 5 weekday calls
    with patch("app.services.bct._fetch_single_date", return_value=2.91) as mock_fetch:
        bct.fetch_rates("USD", "TND", date(2026, 6, 1), date(2026, 6, 7))
    assert mock_fetch.call_count == 5


def test_fetch_rates_skips_none_results():
    # _fetch_single_date returns None for holidays
    call_count = [0]
    def side_effect(code, d):
        call_count[0] += 1
        return None if call_count[0] == 1 else 2.91

    with patch("app.services.bct._fetch_single_date", side_effect=side_effect):
        result = bct.fetch_rates("USD", "TND", date(2026, 6, 2), date(2026, 6, 3))
    # First day skipped (None), second day present
    assert date(2026, 6, 2) not in result
    assert result[date(2026, 6, 3)] == 2.91


def test_fetch_rates_returns_dict_with_correct_dates():
    with patch("app.services.bct._fetch_single_date", return_value=2.9131):
        result = bct.fetch_rates("USD", "TND", date(2026, 6, 2), date(2026, 6, 3))
    assert date(2026, 6, 2) in result
    assert date(2026, 6, 3) in result
    assert result[date(2026, 6, 2)] == 2.9131
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd Backend
pytest tests/test_bct.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.bct'`

- [ ] **Step 3: Implement bct.py**

Create `Backend/app/services/bct.py`:

```python
import httpx
import pandas as pd
from datetime import date, timedelta

BCT_URL = "https://www.bct.gov.tn/bct/siteprod/cours.jsp"


def fetch_rates(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    result: dict[date, float] = {}
    current = from_date
    while current <= to_date:
        if current.weekday() < 5:  # skip Sat=5, Sun=6
            rate = _fetch_single_date(base, current)
            if rate is not None:
                result[current] = rate
        current += timedelta(days=1)
    return result


def _fetch_single_date(currency_code: str, target_date: date) -> float | None:
    date_str = target_date.strftime("%Y%m%d")
    try:
        resp = httpx.get(BCT_URL, params={"date": date_str, "la": "AN"}, timeout=10)
        if resp.status_code != 200:
            return None
        for table in pd.read_html(resp.text):
            if "Sigle" in table.columns and "Valeur" in table.columns:
                row = table[table["Sigle"] == currency_code]
                if not row.empty:
                    raw = str(row.iloc[0]["Valeur"]).replace(",", ".")
                    return float(raw)
    except Exception:
        return None
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd Backend
pytest tests/test_bct.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/bct.py Backend/tests/test_bct.py
git commit -m "feat: add BCT scraper service for USD/TND and EUR/TND"
```

---

## Task 3: Route TND pairs to BCT in rates.py

**Files:**
- Modify: `Backend/app/routers/rates.py` (lines 1–7 and 19–48)
- Modify: `Backend/tests/test_rates.py` (line 25)

- [ ] **Step 1: Update the import and add TND_PAIRS constant**

In `Backend/app/routers/rates.py`, replace lines 1–8:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app import models, schemas
from app.services import frankfurter, analytics, bct

router = APIRouter(prefix="/rates", tags=["rates"])

SUPPORTED_PAIRS = {("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")}
TND_PAIRS = {("USD", "TND"), ("EUR", "TND")}
```

- [ ] **Step 2: Update _ensure_rates_cached to route by pair**

Replace `_ensure_rates_cached` (lines 19–48 in the original file) with:

```python
def _ensure_rates_cached(db: Session, base: str, quote: str, from_date: date, to_date: date):
    """Fetch from appropriate source only if we don't have enough data in DB for the range."""
    total_days = (to_date - from_date).days + 1
    count = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.base_currency == base,
        models.ExchangeRate.quote_currency == quote,
        models.ExchangeRate.date >= from_date,
        models.ExchangeRate.date <= to_date,
    ).count()
    expected_min = max(1, int(total_days * 5 / 7 * 0.8))
    if count >= expected_min:
        return

    try:
        if (base, quote) in TND_PAIRS:
            new_rates = bct.fetch_rates(base, quote, from_date, to_date)
        else:
            new_rates = frankfurter.fetch_rates(base, quote, from_date, to_date)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    source = "bct" if (base, quote) in TND_PAIRS else "frankfurter"
    for rate_date, rate_val in new_rates.items():
        existing = db.query(models.ExchangeRate).filter_by(
            base_currency=base, quote_currency=quote, date=rate_date
        ).first()
        if existing:
            existing.rate = rate_val
        else:
            db.add(models.ExchangeRate(
                base_currency=base, quote_currency=quote,
                rate=rate_val, date=rate_date, source=source
            ))
    db.commit()
```

- [ ] **Step 3: Fix the mock target in test_rates.py**

In `Backend/tests/test_rates.py` line 25, the patch target for the `test_get_historical_rates_returns_list` test still patches `frankfurter.fetch_rates` as a safety net. Since USD/TND now routes to BCT, update the patch:

Replace:
```python
    with patch("app.routers.rates.frankfurter.fetch_rates", return_value={}):
```
With:
```python
    with patch("app.routers.rates.bct.fetch_rates", return_value={}):
```

- [ ] **Step 4: Run the full test suite**

```
cd Backend
pytest tests/ -v
```

Expected: all previously-passing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/routers/rates.py Backend/tests/test_rates.py
git commit -m "feat: route USD/TND and EUR/TND pairs to BCT scraper"
```

---

## Task 4: CSV seed script (TDD)

**Files:**
- Create: `Backend/tests/test_seed_tnd_rates.py`
- Create: `Backend/scripts/seed_tnd_rates.py`

- [ ] **Step 1: Write failing tests**

Create `Backend/tests/test_seed_tnd_rates.py`:

```python
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
        # EUR/TND = 1.0927 (EUR/USD) × 2.9064 (USD/TND)
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
        # Only 2 valid rows, bad_row is skipped
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd Backend
pytest tests/test_seed_tnd_rates.py -v
```

Expected: `ImportError: cannot import name '_seed_from_file' from 'scripts.seed_tnd_rates'`

- [ ] **Step 3: Implement the seed script**

Create `Backend/scripts/seed_tnd_rates.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models

models.Base.metadata.create_all(bind=engine)

_DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "USDTNDEURTND.csv")


def _seed_from_file(db: Session, csv_path: str) -> tuple[int, int]:
    """Parse CSV and upsert USD/TND and EUR/TND rows. Returns (inserted, skipped)."""
    df = pd.read_csv(csv_path, usecols=[0, 1, 2], header=0)
    df.columns = ["date_str", "eur_usd", "usd_tnd"]
    df = df.dropna(subset=["date_str"])

    inserted = 0
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
            else:
                db.add(models.ExchangeRate(
                    base_currency=base, quote_currency=quote,
                    rate=rate, date=d, source="csv"
                ))
            inserted += 1

    db.commit()
    return inserted, skipped


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_CSV
    db = SessionLocal()
    try:
        inserted, skipped = _seed_from_file(db, csv_path)
        print(f"Done: {inserted} rows inserted/updated, {skipped} rows skipped.")
    finally:
        db.close()
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd Backend
pytest tests/test_seed_tnd_rates.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add Backend/scripts/seed_tnd_rates.py Backend/tests/test_seed_tnd_rates.py
git commit -m "feat: add CSV seed script for historical USD/TND and EUR/TND data"
```

---

## Task 5: Run the seed against real data

**Files:**
- No code changes — runs the script against `USDTNDEURTND.csv`

- [ ] **Step 1: Run the seed script**

From `Backend/`:
```
python scripts/seed_tnd_rates.py
```

Expected output:
```
Done: ~3028 rows inserted/updated, N rows skipped.
```
(~1514 CSV rows × 2 pairs = ~3028 rows)

- [ ] **Step 2: Verify data in DB**

```
python -c "
from app.database import SessionLocal
from app import models
db = SessionLocal()
usd = db.query(models.ExchangeRate).filter_by(base_currency='USD', quote_currency='TND').count()
eur = db.query(models.ExchangeRate).filter_by(base_currency='EUR', quote_currency='TND').count()
print(f'USD/TND rows: {usd}')
print(f'EUR/TND rows: {eur}')
db.close()
"
```

Expected:
```
USD/TND rows: ~1514
EUR/TND rows: ~1514
```

- [ ] **Step 3: Smoke-test the live API endpoints**

Start the backend: `uvicorn app.main:app --reload`

Then in another terminal:
```
curl "http://localhost:8000/api/v1/rates/USD/TND/daily-change" | python -m json.tool
curl "http://localhost:8000/api/v1/rates/USD/TND/performance?period=weekly" | python -m json.tool
curl "http://localhost:8000/api/v1/rates/EUR/TND/volatility" | python -m json.tool
curl "http://localhost:8000/api/v1/alerts/USD/TND" | python -m json.tool
```

Expected: all return `200 OK` with valid JSON — no more 422 errors.

- [ ] **Step 4: Run the full test suite one final time**

```
cd Backend
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: BCT scraper + CSV historical seed resolves 422 errors for TND pairs"
```
