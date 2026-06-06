# Best Free FX Datasets & APIs for the Intern Dashboard (June 2026)

## TL;DR
- *Use the Frankfurter API (api.frankfurter.dev) as your primary source.* It is free, needs no API key, has no quotas, returns clean JSON/CSV that drops straight into pandas, and — critically — its expanded multi-central-bank dataset now covers all four of your required pairs (EUR/USD, GBP/USD, USD/TND, EUR/TND) with daily history far exceeding your 1–2 year window. This single source can power the whole dashboard.
- *For redundancy on TND, add fawazahmed0's free CDN currency-api* (no key, no limits, supports TND) and **Yahoo Finance via yfinance** (tickers USDTND=X, EURTND=X, EURUSD=X); for a downloadable static CSV backup, grab a Kaggle EUR/USD OHLC dataset.
- *Skip the registration-gated APIs* (Open Exchange Rates, Fixer, freecurrencyapi, exchangerate.host/APILayer) for this project: their free tiers gate historical/time-series behind paid plans, lock you to a fixed base currency, or cap you as low as 100 requests/month — all friction your interns don't need when Frankfurter is open.

## Key Findings
1. *Frankfurter is the standout.* It requires no API key, has no daily/monthly caps, is open source, and serves both JSON and CSV. The project was substantially expanded from the old 31-currency ECB-only set; the frankfurter.dev homepage now states verbatim: "Frankfurter tracks daily exchange rates from 84 central banks, covering 201 currencies back to 1948. The public API lives at api.frankfurter.dev. It requires no API key." The live currency list includes North African/Middle East currencies the ECB never published (Algerian Dinar DZD, Egyptian Pound EGP, UAE Dirham AED, Bahraini Dinar BHD), confirming TND is now in scope.
2. *TND is the binding constraint.* The Tunisian Dinar is NOT in the classic 31-currency ECB reference set, so any ECB-only API (old Frankfurter, freecurrencyapi free tier, Formicka/exchangerate.host) cannot serve USD/TND or EUR/TND. The sources that DO offer free TND daily history are: the new Frankfurter, fawazahmed0's CDN API, Yahoo/yfinance, and (with registration) CurrencyFreaks/Open Exchange Rates.
3. *Most "free historical" APIs are bait.* Open Exchange Rates, Fixer, freecurrencyapi, and exchangerate.host all advertise history back to 1999 but gate time-series or historical endpoints behind paid tiers, or restrict the free base currency.
4. *Kaggle/GitHub static datasets* are best as offline backups: rich EUR/USD OHLC history but rarely include TND.
5. *The analysis the dashboard needs* (volatility, daily change, risk alerts) is trivial on close-price time series via pandas pct_change(), rolling().std(), and threshold logic — no OHLC strictly required, though OHLC enables intraday-range volatility.

## Details

### A. Free APIs (recommended path)

*1. Frankfurter — TOP PICK*
- URL / docs: https://frankfurter.dev ; API host https://api.frankfurter.dev (v2 current; v1 still supported; legacy host api.frankfurter.app)
- Currencies: 201 currencies from 84 central banks; includes EUR, USD, GBP, and TND. EUR/USD, GBP/USD, USD/TND, EUR/TND all available.
- Date range: classic ECB series from 1999-01-04; some currencies back to 1948; TND from 1998 — well beyond your 1–2 year need.
- Format: JSON (default), CSV (append .csv or Accept: text/csv), NDJSON for streaming large ranges.
- Registration / key: NONE. No quotas; only anti-abuse rate limiting.
- Updates: every working day around 16:00 CET; weekday-only (no weekend rows). Today's value is not stable until published.
- Why useful: clean, key-free, covers every required pair, returns a date-keyed time series ideal for computing daily returns, rolling volatility, and risk-alert thresholds. Commercial use OK.
- Example endpoints:
  - v1 time series: https://api.frankfurter.dev/v1/2024-01-01..2024-12-31?base=EUR&symbols=USD,TND
  - v2 time series: https://api.frankfurter.dev/v2/rates?from=2024-01-01&to=2024-12-31&base=USD&quotes=TND
  - single pair: https://api.frankfurter.dev/v2/rate/EUR/USD
- Python:
  
  import requests, pandas as pd
  r = requests.get("https://api.frankfurter.dev/v1/2024-01-01..2025-12-31",
                   params={"base":"EUR","symbols":"USD,TND,GBP"}).json()
  df = pd.DataFrame(r["rates"]).T
  df.index = pd.to_datetime(df.index); df = df.sort_index()
  

*2. fawazahmed0 currency-api (jsDelivr CDN) — best key-free TND backup*
- URL / repo: https://github.com/fawazahmed0/exchange-api
- Currencies: 200+ including crypto and metals; TND confirmed present ("tnd" appears in the live currency JSON).
- Date range: reliable daily history from ~March 2024 onward (the older GitHub-hosted @1 series back to ~2020 became unreliable after GitHub removed the original repo in March 2024 for size). Covers roughly the last ~15 months cleanly — enough for a 1-year window but borderline for a full 2 years.
- Format: JSON / minified JSON via CDN.
- Registration / key: NONE; no rate limits.
- Endpoints (date = latest or YYYY-MM-DD):
  - https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@2024-03-06/v1/currencies/usd.json
  - single pair: .../v1/currencies/usd/tnd.json and .../v1/currencies/eur/tnd.json
  - fallback host: https://2024-03-06.currency-api.pages.dev/v1/currencies/usd/tnd.json
- Why useful: zero friction, good for a redundant TND feed; build a date loop to assemble a time series, and include the documented fallback host.

**3. Yahoo Finance via yfinance — OHLC + TND cross-check**
- Tickers: EURUSD=X, GBPUSD=X, USDTND=X (also TND=X), EURTND=X.
- Date range: EURUSD=X history starts 2003-12-01; TND crosses exist but have shorter/patchier daily history — verify at runtime via df.index.min().
- Format: pandas DataFrame (OHLC; Volume is always 0 for FX).
- Registration / key: NONE, but yfinance is unofficial (scrapes Yahoo's public endpoints) and can break intermittently.
- Python:
  
  import yfinance as yf
  data = yf.download(["EURUSD=X","GBPUSD=X","USDTND=X","EURTND=X"],
                     start="2024-06-01", end="2026-06-04", interval="1d")
  close = data["Close"]
  

*4. Registration-gated APIs (note, but deprioritize)*
- *Open Exchange Rates* (https://openexchangerates.org): free 1,000 req/mo, key required; per its Plans & Pricing Guide, "Our Forever Free Plan ... includes hourly updates for all rates, historical data and up to 1,000 requests per month. Multiple base currencies, time-series and conversion requests are not included ... The base currency on our Free plan is always USD." 200+ currencies incl. TND; EUR/TND must be derived as a USD cross, and time-series requires looping single-date calls.
- *Fixer.io* (https://fixer.io): free tier is 100 requests/month, key required, *EUR is the only base currency on the free account, HTTP-only*; per its GitHub README, "Get historical rates for any day since 1999."
- *freecurrencyapi.com* (https://freecurrencyapi.com): free 5,000 req/mo but the free tier is exactly *32 currencies* (an ECB-style set; TND unlikely) — verbatim: "Features the most important 32 international currencies ... No commercial use allowed." Single-date historical only on free.
- *exchangerate.host / exchangeratesapi.io / Fixer* (APILayer family): now require a free access_key; small monthly free caps (exchangeratesapi.io free is 100 req/mo).
- *CurrencyFreaks* (https://currencyfreaks.com): free 1,000 req/mo, *no credit card*, 1,020 currencies incl. TND, USD base on free; per its FAQ historical data is available "from 1984-11-28 ... which varies on Historical Data Limits from which date each currency is available." The best registration-based fallback for TND if you need more than ~15 months from a single keyed provider.
- *Alpha Vantage* (https://www.alphavantage.co): free key, FX_DAILY OHLC, but only 25 requests/day — too slow for bulk backfill.
- *FRED* (https://fred.stlouisfed.org): excellent free daily majors (DEXUSEU for USD/EUR, DEXUSUK for USD/GBP) back to 1999/1971, CSV/API, but *Tunisia series are annual/monthly only — no daily TND.*

### B. Static datasets (offline backups)

*Kaggle* (free account required to download; CSV):
- imetomi/eur-usd-forex-pair-historical-data-2002-2019 — EUR/USD, 2002–2019, full OHLC (+ minute data). Dated but rich.
- gabrielmv/eurusd-daily-historical-data-20012019 — EUR/USD daily, 2001–2019.
- dhruvildave/currency-exchange-rates / thebasss/currency-exchange-rates (51 currencies 1995–2018) / asaniczka/forex-exchange-rate-since-2004-updated-daily / konradb/foreign-exchange-rates-daily-updates — broad multi-currency daily sets; some may include TND (verify the column after download). The "updated daily" ones give recency.
- Note: Kaggle vote/download counts could not be retrieved (login wall); ranges from dataset metadata.

*GitHub* (direct CSV / downloaders):
- philipperemy/FX-1-Minute-Data — all major/cross pairs, 1-minute & tick, 2000–2024+, from histdata.com. No TND. Great for EUR/USD, GBP/USD intraday OHLC.
- ejtraderLabs/historical-data — majors incl. EURUSD, GBPUSD via raw.githubusercontent.com CSV; pd.read_csv(url) directly. No TND.
- fxcm/MarketData — majors/crosses CSV by week/year. No TND.

### C. Computing the dashboard metrics
On any close-price series in pandas:
import numpy as np
ret = df.pct_change()                            # daily change
vol = ret.rolling(21).std()                      # ~1-month rolling volatility
ann_vol = ret.rolling(21).std()*np.sqrt(252)     # annualized
alert = ret.abs() > (3*ret.rolling(63).std())    # risk alert: >3σ daily move
A 21-day rolling window (~1 trading month) is the common convention; annualize by √252.

## Recommendations
1. *Tomorrow (Day 1): build on Frankfurter.* Point the ingestion layer at api.frankfurter.dev time-series endpoints for EUR/USD, GBP/USD, USD/TND, EUR/TND. No signup, so interns can start immediately. Cache responses to local CSV/parquet to avoid re-fetching.
2. *Add one redundancy for TND:* wire fawazahmed0's CDN as a fallback feed and/or pull yfinance for an independent cross-check; reconcile any divergence (sources can differ ~0.05% from ECB reference).
3. *Keep a static CSV in the repo* (a Kaggle EUR/USD OHLC set or a one-time Frankfurter CSV dump) so the dashboard renders even if a network call fails.
4. *If you outgrow the free window* (need >~15 months of TND from a single keyed provider, or higher request volumes): register for *CurrencyFreaks* (no card, TND, history to 1984-11-28) before considering any paid plan.
5. *Benchmarks that would change the plan:* if you need intraday (sub-daily) volatility → switch to histdata.com via philipperemy/FX-1-Minute-Data (majors only); if you need TND further back than ~1998 daily → no free source exists, escalate to a paid provider; if request volume exceeds anti-abuse limits → self-host Frankfurter via Docker (open source).

## Caveats
- *Frankfurter TND verification:* the older GitHub issue tracker (lineofflight/frankfurter Issue #144) still lists TND as a "requested" currency, but the live v2 API now returns expanded coverage including non-ECB North African currencies (DZD, EGP, AED, BHD) and an independent live query returned a EUR/TND rate (~3.376) consistent with market quotes (~3.385 on Investing.com). Confirm the TND endpoint returns data on Day 1 before committing.
- *fawazahmed0 history depth:* reliable free daily history effectively starts ~March 2024 after the repo migration; old dated URLs (pre-2024) are unreliable. Not a full-2-year source.
- *yfinance* is unofficial and intended for personal/research use; TND cross history is short and can have gaps; FX volume is always 0.
- *Registration-gated APIs* advertise long histories but lock time-series/historical or non-USD/EUR bases behind paid tiers — read the free-tier fine print.
- *Kaggle* download/vote metrics unverified (login wall); several broad sets only probably include TND — confirm the currency column after download.
- *Rate quality:* ECB/Frankfurter are reference (mid) rates, not tradeable quotes, and TND in particular is a restricted currency with official rates set by the Central Bank of Tunisia; fine for a volatility/risk dashboard, not for execution.
