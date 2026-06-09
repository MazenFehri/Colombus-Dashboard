# Hedge Advisor — Critical Review

**Date:** 2026-06-09  
**Scope:** Logic, math, data quality, and structural gaps in the current implementation.

---

## Summary

The current implementation is a reasonable v1 demo but has several real flaws — some cosmetic,
some that would produce wrong or misleading output in a real treasury context. They fall into
four buckets: **wrong inputs**, **wrong math**, **missing context**, and **AI weaknesses**.

---

## 1. Option A — Heuristic Signal

### 1.1 The 30-day window is arbitrary and can lie

`change_30d_pct` is used as the sole directional indicator. It is the performance over the
last calendar month — nothing more. Two problems:

**Problem — The lookback horizon has nothing to do with the business's payment date.**
A company paying in 45 days cares about what happens in the next 45 days, not what happened
in the last 30. The correct input is the rate change over the period from now to the settlement
date. We don't ask for a settlement date.

**Problem — A recovery disguised as a trend.**
If the rate spiked hard against the user 3 weeks ago and has been recovering since, the 30-day
number might show neutral or even favourable — while the pair is still above where it was.
Example: EUR/TND was 3.30 → spiked to 3.50 → sits at 3.40 now. The 30d change is +3%.
The real trend for the last 7 days is bearish. The signal fires CONSIDER_FORWARD based on the
spike that's already past, not based on where things are going. We should also use
the short-term trend (`calc_trend`, which we already compute) as a forward-looking filter.

### 1.2 The direction logic is purely binary

`rate_moving_against` is a binary flag — either the rate moved against you or it didn't.
There is no magnitude check. A 0.01% adverse move fires the same flag as a 5% adverse move.
The signal is only differentiated by vol and risk level, not by how severely the rate moved.
A minor drift in a turbulent regime → CONSIDER_FORWARD. That's too aggressive.

A better approach: require the adverse move to exceed the pair's typical range
(e.g. > 0.5 rolling std) before flagging it as "moving against."

### 1.3 The vol threshold is a hardcoded guess

```python
_VOL_ELEVATED = {"TND": 0.03, "default": 0.07}
```

These are guesses. 3% for TND and 7% for majors are plausible, but they are never
validated against the actual distribution of `annualized_vol` for each pair over history.
We already compute `vol_regime` from `calc_vol_regime` (elevated / normal / compressed)
using a data-driven percentile approach. We should use `vol_regime == "elevated"` from
the snapshot instead of re-inventing a threshold here. Two vol elevation checks doing
different things is inconsistent.

### 1.4 The signal ignores the forward curve itself

The forward premium is the market's own CIP-implied estimate. If TND/USD trades at
a +1.6% six-month forward premium, that already tells an importer "the market expects
to pay 1.6% more in 6 months — locking in avoids that cost."

We compute this premium (Option B) but never feed it back into the heuristic signal.
A NEUTRAL signal can coexist with a steep forward curve, which is contradictory:
the forward curve says "hedge," the signal says "no strong view."

### 1.5 Importer/Exporter is too coarse

Real business FX exposure has nuance:
- A company might be 70% naturally hedged (revenue in USD, costs in USD).
- A partial hedger might want to hedge 50% forward and leave 50% on spot.
- A business with rolling monthly payments doesn't make a single one-shot decision.

The binary toggle collapses all of this into one flag. The signal output is therefore
generic advice, not actionable guidance for a specific exposure.

---

## 2. Option B — CIP Forward Rates

### 2.1 Using policy rates instead of term money-market rates

This is the most significant mathematical error.

The CIP formula requires the **money-market rate for the same tenor as the forward**.
A 3-month forward should use the 3-month interbank lending rate — SOFR (USD), EURIBOR (EUR),
or TUNIBOR (TND) — not the central bank policy rate.

| Currency | Policy rate (what we use) | 3M term rate (what CIP needs) |
|----------|--------------------------|-------------------------------|
| USD | Fed funds 3.70% | 3M SOFR ≈ 4.3–4.5% (historically diverges 50–100 bps) |
| EUR | ECB deposit 2.10% | 3M EURIBOR ≈ 2.4–2.8% |
| TND | BCT key rate 7.00% | TUNIBOR 3M (harder to source; often 50–150 bps above key rate) |

Using policy rates underestimates the forward premium for USD and EUR and likely
underestimates even more for TND. Our 3M EUR/TND forward at +1.22% could be closer
to +1.8% with proper term rates. The numbers we show are directionally right but
numerically wrong.

### 2.2 Simple interest, not the correct day-count convention

We use simple (linear) interest: `1 + r × t`

Real FX forward pricing uses:
- **ACT/360** for USD and EUR money markets
- **ACT/365** for GBP, TND (typically follows Actual/365 conventions)

For 3M: `t = 91/360 ≈ 0.2528` (ACT/360), not `t = 0.25` (exact quarter).
For 6M: `t = 184/360 ≈ 0.5111` (ACT/360), not `t = 0.50`.

The error is small (<0.05%) but it means the numbers in the table don't match what
a bank would actually quote, which makes the disclaimer about "indicative only" even
more load-bearing than it sounds.

### 2.3 Hardcoded rates break silently

The rates are constants with no expiry date:
```python
_INTEREST_RATES = {"TND": 0.0700, "USD": 0.0370, "EUR": 0.0210}
```

The BCT cut its key rate from 8% to 7% in 2024. The Fed has been cutting since late 2024.
If these rates go stale, the forward table silently produces wrong numbers. There is no
timestamp, no staleness check, no warning to the user that these rates might be outdated.
A user who doesn't read the footnote will treat these as current market rates.

### 2.4 No bid-ask spread means the "rate" isn't actionable

We show one number per tenor (e.g. EUR/TND 3M: 3.4171). A real bank quotes:
- **Bid:** 3.4100 (the rate at which the bank buys EUR from you)
- **Ask:** 3.4240 (the rate at which the bank sells EUR to you)

The spread on EUR/TND can be 30–80 pips wide for a Tunisian SME. Our midpoint rate
shows the best possible outcome — not the rate a business would actually transact at.
Showing a single precise number (3.4171) without the spread context implies a precision
that doesn't exist in practice.

### 2.5 GBP is just silently absent

For GBP/USD, the forward table disappears without explanation (beyond a footnote).
The user sees signal + narrative but no numbers. If Reuters/LSEG data is wired in,
GBP SONIA/SONIA OIS rates are readily available — this gap goes away.

---

## 3. Option C — AI Narrative

### 3.1 The volatility is passed as a raw fraction, not a percentage

In the prompt we pass:
```
f"Annualised volatility: {annualized_vol:.2%}"
```

The `:2%` format actually does multiply by 100 and add %, so `0.0146` becomes `1.46%`.
That part is correct. But earlier in the context block in `hedge_engine.py`:

```python
f"Annualised vol: {annualized_vol:.2%}\n"
```

This is fine. However the risk level string (`"low"` in lower case) and the signal
string (`"CONSIDER_FORWARD"` in upper snake case) look inconsistent in the same prompt.
The AI normalises around them but it produces occasional awkward phrasing like
*"the SPOT_REASONABLE signal suggests..."* when it should say *"the Spot Reasonable signal."*

### 3.2 The narrative is never cached — a toggle flip makes a Groq call every time

The user switching from Importer → Exporter → Importer in 10 seconds generates
3 Groq API calls for data that hasn't changed. The narrative is keyed on
`(pair, exposure, asOf)` in the React Query cache (`staleTime: 2 * 60 * 1000`),
so at least the frontend dedups rapid re-fires. But on the backend there is no
server-side cache at all — every request hits Groq regardless.

### 3.3 The AI has no access to news

The Market Intelligence card (`ai_service.py`) passes 3 recent headlines to the LLM
so it can ground its commentary in real events. The Hedge Advisor prompt sends none.

This means the AI might give generic directional advice ("the rate has been rising") while
a Reuters headline says *"BCT announces emergency rate hike"* — context that would change
the hedging advice completely. Feeding the same headlines we already fetch for the Market
Intelligence card into the Hedge Advisor prompt would cost nothing extra and would make
the advice much more grounded.

### 3.4 The AI can hallucinate forward rates

The AI receives the CIP forward rates in its prompt. There is nothing stopping it from
inventing a different number in its narrative (e.g. saying *"the 3M forward sits near 3.50"*
when we computed 3.42). We never validate the AI output against the computed data.
A post-processing step that checks for any number in the narrative that looks like a rate
and compares it to our computed rates would catch obvious hallucinations.

---

## 4. Structural missing inputs

These aren't bugs — they are inputs the feature fundamentally needs to give good advice
but currently doesn't ask for.

### 4.1 Settlement date (most important missing input)

The single most important variable in any hedging decision is **when** the business
needs the currency. Without it:

- We can't select the right tenor (we show all three and let the user figure it out).
- The heuristic uses a 30-day trend regardless of whether the payment is in 2 weeks or 8 months.
- The AI gives advice in a vacuum ("the 3M rate is X") rather than advice aligned to the actual risk window.

A simple date picker labelled "When do you need this currency?" would make every
other part of the feature more meaningful.

### 4.2 Transaction size

The cost-benefit of a forward changes with notional. A 100 TND transaction doesn't justify
the overhead of a forward agreement. A 500,000 TND payment absolutely does.
We have no idea which we're dealing with.

### 4.3 There is no FX options alternative

Forward contracts are not the only hedging instrument. An FX option gives the right but
not the obligation to transact at a fixed rate — it captures upside while limiting downside.
In volatile regimes, options may be superior to forwards. We never mention this. The binary
"spot vs forward" framing misses the option entirely.

---

## 5. Where Reuters API changes everything

The Reuters News API (LSEG/Refinitiv) provides three things we currently lack:

### 5.1 Real forward rates from the interbank market

Instead of computing CIP estimates from policy rates, Reuters/Refinitiv quotes
**actual live forward rates** (NDF for TND, outright forwards for EUR/USD, GBP/USD).
These include:
- Proper bid/ask spread
- Market-implied term rates already baked in
- Settlement conventions correct per currency
- Updated in real time

This completely replaces Option B's math. We show what the market actually prices, not
what we calculate.

### 5.2 Proper interest rate data (SOFR, EURIBOR, TUNIBOR)

Reuters provides the term rate curves — 1M, 3M, 6M, 1Y overnight index swap (OIS) rates
for USD (SOFR), EUR (EURIBOR/€STR), and GBP (SONIA). If we keep doing CIP ourselves, we
should at least use proper term rates instead of policy rates. This fixes the biggest
mathematical error (§2.1) without abandoning the CIP approach.

### 5.3 FX-tagged news, not Google RSS scraping

Google News RSS is:
- Inconsistent in tagging (often returns generic business news)
- No guarantee of relevance to a specific currency pair
- Subject to rate limits and silent failures
- Not designed for financial use

Reuters provides structured, FX-tagged news with metadata:
- Currency pair tags (e.g. `EUR_TND`, `USD_TND`)
- Story type (central bank, economic data, geopolitical)
- Sentiment signals
- Timestamps with timezone

For the BCT (Banque Centrale de Tunisie), Reuters is one of the only consistent
English-language sources of official rate decisions and monetary policy commentary.
The Google RSS almost never catches BCT news.

### 5.4 Implied volatility (the real measure of FX uncertainty)

Our `annualized_vol` is **historical volatility** — it measures how much the rate
*has* moved. The market's actual assessment of how much it *will* move is
**implied volatility (IV)** from FX options, which Reuters/Refinitiv quotes in real time.

| | Historical vol (what we compute) | Implied vol (what Reuters provides) |
|-|----------------------------------|-------------------------------------|
| Backward-looking? | Yes | No — forward-looking |
| Captures upcoming events? | No | Yes (e.g. vol spikes before a BCT meeting) |
| Used by banks for forwards? | No | Yes |
| Example EUR/USD | ~6% annualised | Can jump to 12% around ECB decisions |

In a world where an ECB rate decision is in 3 days, implied vol will be elevated and
our historical vol will look calm — completely wrong signal for the hedge decision.

---

## 6. Priority ranking of fixes

| Rank | Issue | Effort | Impact |
|------|-------|--------|--------|
| 1 | Add settlement date input → match tenor to payment | Low | Very High |
| 2 | Use `vol_regime` from snapshot instead of hardcoded thresholds | Very Low | Medium |
| 3 | Feed news headlines into the Hedge Advisor prompt | Low | High |
| 4 | Validate AI output against computed forward rates | Low | Medium |
| 5 | Show forward premium as cost context (not just %) | Low | Medium |
| 6 | Switch from policy rates to term rates (SOFR / EURIBOR) | Medium | High (math accuracy) |
| 7 | Add server-side cache keyed on (pair, exposure, date) | Medium | Medium (cost/perf) |
| 8 | Integrate Reuters API for real forward quotes | High | Very High (accuracy) |
| 9 | Add FX options as a third alternative in the narrative | High | High (completeness) |

Items 1–5 require no new external dependencies and could ship in the next iteration.
Items 6–9 depend on Reuters API access or additional data work.
