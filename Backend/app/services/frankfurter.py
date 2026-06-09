import httpx
from datetime import date

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"
FAWAZAHMED_BASE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1"


def fetch_rates(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    """Fetch rates from Frankfurter; fall back to fawazahmed0. Returns {date: rate}."""
    try:
        return _fetch_frankfurter(base, quote, from_date, to_date)
    except Exception:
        pass
    try:
        return _fetch_fawazahmed(base, quote, to_date)
    except Exception:
        raise RuntimeError("Exchange rate data unavailable — both sources failed")


def _fetch_frankfurter(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    url = f"{FRANKFURTER_BASE}/{from_date}..{to_date}"
    params = {"base": base, "symbols": quote}
    resp = httpx.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    result: dict[date, float] = {}
    for date_str, rates in data.get("rates", {}).items():
        if quote in rates:
            result[date.fromisoformat(date_str)] = float(rates[quote])
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


def _fetch_fawazahmed_range(base: str, quote: str, from_date: date, to_date: date) -> dict[date, float]:
    """Fetch a date range from fawazahmed0 by hitting each date's versioned CDN URL."""
    from datetime import timedelta
    result: dict[date, float] = {}
    current = from_date
    while current <= to_date:
        date_str = current.isoformat()
        url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date_str}/v1/currencies/{base.lower()}.json"
        try:
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get(base.lower(), {}).get(quote.lower())
                if rate is not None:
                    result[current] = float(rate)
        except Exception:
            pass
        current += timedelta(days=1)
    return result
