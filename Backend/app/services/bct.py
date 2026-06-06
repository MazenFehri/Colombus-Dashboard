import io
import httpx
import pandas as pd
from datetime import date, timedelta

BCT_URL = "https://www.bct.gov.tn/bct/siteprod/cours.jsp"


def fetch_rates(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    result: dict[date, float] = {}
    attempted = 0
    current = from_date
    while current <= to_date:
        if current.weekday() < 5:  # skip Sat=5, Sun=6
            attempted += 1
            rate = _fetch_single_date(base, current)
            if rate is not None:
                result[current] = rate
        current += timedelta(days=1)
    if not result and attempted > 0:
        raise RuntimeError("BCT data unavailable")
    return result


def _fetch_single_date(currency_code: str, target_date: date) -> float | None:
    date_str = target_date.strftime("%Y%m%d")
    try:
        resp = httpx.get(BCT_URL, params={"date": date_str, "la": "FR"}, timeout=10)
        if resp.status_code != 200:
            return None
        for table in pd.read_html(io.StringIO(resp.text), decimal=",", thousands="."):
            if "Sigle" in table.columns and "Valeur" in table.columns:
                row = table[table["Sigle"] == currency_code]
                if not row.empty:
                    return float(row.iloc[0]["Valeur"])
    except Exception:
        return None
    return None
