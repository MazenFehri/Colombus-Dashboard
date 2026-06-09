import httpx
from datetime import date

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"
FAWAZAHMED_BASE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1"


def fetch_rates(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    """Fetch rates from Frankfurter v2; fall back to fawazahmed0. Returns {date: rate}."""
    try:
        return _fetch_frankfurter(base, quote, from_date, to_date)
    except Exception:
        pass
    try:
        return _fetch_fawazahmed(base, quote, to_date)
    except Exception:
        raise RuntimeError("Exchange rate data unavailable — both sources failed")


def _fetch_frankfurter(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    # Frankfurter v2 /rates returns a flat list: [{"date","base","quote","rate"}, ...].
    # A from/to range yields one entry per business day in the window.
    url = f"{FRANKFURTER_BASE}/rates"
    params = {"base": base, "quotes": quote, "from": from_date.isoformat(), "to": to_date.isoformat()}
    resp = httpx.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    result: dict[date, float] = {}
    for entry in data:
        if entry.get("quote") == quote:
            result[date.fromisoformat(entry["date"])] = float(entry["rate"])
    return result


def _fetch_fawazahmed(base: str, quote: str, target_date: date) -> dict[date, float]:
    url = f"{FAWAZAHMED_BASE}/currencies/{base.lower()}.json"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    rate = data.get(base.lower(), {}).get(quote.lower())
    if rate is None:
        raise ValueError(f"No rate found for {base}/{quote}")
    return {target_date: float(rate)}
