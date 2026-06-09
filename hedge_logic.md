# Hedge Advisor — Logic Documentation

**Status:** Implemented  
**Date:** 2026-06-09  
**Related:** `forward_spot.md` (design options), `logic.md` (core risk logic)

---

## What this feature does

Given a currency pair, a date, and whether the business is an **importer** or **exporter**,
the Hedge Advisor answers one question:

> *Should this business transact at the spot rate today, or lock in a forward contract?*

It combines three independent outputs into one panel:

| Option | What it produces | How |
|--------|-----------------|-----|
| **A** | Heuristic signal | Rule-based logic on trend + vol + risk |
| **B** | CIP forward rates | Covered interest parity formula |
| **C** | AI narrative | Groq LLM interprets A + B in plain language |

---

## Option A — Heuristic Signal

### Inputs

| Input | Source | Description |
|-------|--------|-------------|
| `change_30d_pct` | `calc_performance(df, "monthly")` | 30-day % change in the spot rate |
| `annualized_vol` | `calc_volatility(df)` | Rolling 21-day std × √252 |
| `risk_level` | `classify_risk(daily_change, spike, quote)` | LOW / MEDIUM / HIGH |
| `exposure` | User toggle | `importer` or `exporter` |

### The direction problem

The same rate movement is good news for one party and bad news for the other:

| Exposure | Hurt when rate… | Because… |
|----------|----------------|----------|
| **Importer** (will BUY foreign currency) | Rises | They pay more |
| **Exporter** (will SELL/receive foreign currency) | Falls | They earn less |

So `rate_moving_against` is computed relative to the user's exposure:

```
if exposure == "importer":
    rate_moving_against = change_30d_pct > 0   # rising rate hurts importer
else:
    rate_moving_against = change_30d_pct < 0   # falling rate hurts exporter
```

### Volatility threshold

Whether volatility is "elevated" depends on the pair's quote currency.
TND is a BCT-managed currency — it moves far less than floating pairs,
so the bar for "elevated" is much lower:

| Quote | Vol threshold | Rationale |
|-------|--------------|-----------|
| TND | 3% annualised | BCT-managed; typical range 1–3% |
| USD / EUR / GBP (default) | 7% annualised | Floating; typical range 3–10% |

### Decision logic

```
if rate_moving_against AND (vol_elevated OR risk == HIGH):
    signal = CONSIDER_FORWARD
    → Locking today's rate reduces risk

elif rate_moving_in_favour AND NOT vol_elevated AND NOT risk == HIGH:
    signal = SPOT_REASONABLE
    → Staying on spot may benefit the business

else:
    signal = NEUTRAL
    → No strong directional signal
```

The rule intentionally has a conservative bias: `CONSIDER_FORWARD` fires only when
the rate is actively moving against the user **and** conditions are stressed. A neutral
market never forces a recommendation.

---

## Option B — CIP Forward Rates

### The formula

A forward rate is not a prediction — it is derived from the **interest-rate differential**
between the two currencies via **Covered Interest Parity (CIP)**:

```
Forward = Spot × (1 + r_quote × t) / (1 + r_base × t)
```

Where:
- `Spot` — today's exchange rate (units of quote per base)
- `r_quote` — annual interest rate of the quote currency
- `r_base` — annual interest rate of the base currency
- `t` — tenor in years (1M = 1/12, 3M = 0.25, 6M = 0.50)

### Interest rates (as of 2026-06)

| Currency | Rate | Source |
|----------|------|--------|
| TND | 7.00% | BCT key rate |
| USD | 3.70% | Fed funds upper bound |
| EUR | 2.10% | ECB deposit rate |
| GBP | — | Not configured → forward rates not shown |

### What the pct_diff means

`pct_diff = (forward − spot) / spot × 100`

A **positive** pct_diff means the quote currency **weakens** in the forward market —
it costs more quote to buy one unit of base at the future date. This is called a
**forward premium** on the base currency (or **forward discount** on the quote).

A **negative** pct_diff is the reverse — the base weakens forward.

### Why TND always shows a forward discount

TND has the highest policy rate (7%). According to CIP, high-rate currencies must
trade at a forward discount to prevent arbitrage — if TND earned more interest AND
strengthened forward, investors could borrow cheaply in EUR/USD, park in TND, and
profit risk-free. The market prices this out:

| Pair | Spot | 3M Forward | Interpretation |
|------|------|-----------|----------------|
| USD/TND | 2.91 | 2.93 | +0.82% — TND weakens vs USD forward |
| EUR/TND | 3.38 | 3.42 | +1.22% — TND weakens vs EUR forward |
| EUR/USD | 1.16 | 1.165 | +0.40% — USD weakens vs EUR forward (USD earns more) |
| GBP/USD | — | — | No GBP rate configured |

This is financially correct and matches real interbank forward quotes
(before spread and credit adjustments).

### What the forward rate table tells a treasurer

The table answers: *"If I lock in a forward contract now, what rate do I get?"*

- The forward is always available at that rate — no market risk.
- The spot at maturity could be better or worse than the forward.
- Choosing forward = certainty. Choosing spot = exposure.

Whether certainty is worth the implied premium/discount is what the heuristic
signal and AI narrative help decide.

---

## Option C — AI Narrative

The AI (Groq `llama-3.3-70b-versatile`) receives a structured prompt containing:

- Pair, exposure direction, resolved date
- Spot rate + all CIP forward rates (if available)
- 30-day change, annualised vol, risk level
- The heuristic signal and its one-line reason
- The last 7 days of rate history

It is instructed to write 3–4 sentences covering:
1. What the market is doing and why it matters for this specific business.
2. Why the heuristic suggests the given signal.
3. One practical consideration referencing forward rate levels.
4. A one-sentence disclaimer.

The narrative is **always fresh** (not cached) because the exposure direction is
user-controlled — the same market data produces different advice for an importer
vs an exporter.

---

## End-to-end flow

```
User picks pair + exposure + (optional) as_of date
        │
        ▼
Backend: GET /api/v1/hedge/{base}/{quote}/recommendation
        │
        ├── load 400 days of rate data (same window as AI commentary)
        ├── resolve to nearest prior trading day
        │
        ├── A: compute_signal(change_30d, vol, risk, exposure)
        │         └── returns signal + short_reason + context block
        │
        ├── B: compute_forward_rates(spot, base, quote)
        │         └── CIP for 1M / 3M / 6M ([] if GBP)
        │
        └── C: build prompt → Groq → narrative
                   (includes A context + B forward levels)
        │
        ▼
Frontend: HedgeAdvisor card
        ├── ExposureToggle (Importer / Exporter)
        ├── Signal badge (CONSIDER_FORWARD / SPOT_REASONABLE / NEUTRAL)
        ├── CIP forward rate table (hidden for GBP/USD)
        ├── Stats row (spot, 30d change, vol, risk)
        ├── AI narrative
        └── Disclaimer
```

---

## Edge cases

| Situation | Behaviour |
|-----------|-----------|
| < 21 observations | `annualized_vol = 0.0` → vol_elevated = false; heuristic degrades gracefully |
| < 2 observations | `change_30d = 0.0` → NEUTRAL signal |
| GBP/USD | `forward_rates = []` → table hidden; AI still gets heuristic context |
| Groq unavailable | `narrative = "AI narrative unavailable: <error>"` — rest of card still renders |
| as_of = weekend / holiday | Resolved to nearest prior trading day |

---

## Limitations and caveats

1. **Forward rates are indicative only.** Real bank forward quotes include bid-ask
   spread, credit/counterparty margin, and regulatory costs. The CIP rate is the
   fair theoretical midpoint, not a price you can trade at.

2. **Interest rates are hardcoded constants.** They should be updated when the BCT,
   Fed, or ECB changes policy. A future improvement could pull them from a rate feed.

3. **GBP is not covered** for forward rates because no GBP IR was configured.
   The heuristic signal still works for GBP/USD.

4. **The heuristic ignores transaction size and tenor.** A 30-day change is used
   as a proxy for trend regardless of when the business actually needs the currency.
   A more precise implementation would take the payment date and compare the
   corresponding forward tenor directly.

5. **No de-escalation.** The heuristic does not consider how far in-the-money a
   forward already is. It is a go-forward signal, not a position management tool.

---

## Future improvements

- Wire in a live interest-rate feed so rates update automatically.
- Add GBP rate to enable GBP/USD forward quotes.
- Let the user input their target settlement date → use the matching tenor forward.
- Show historical forward premium/discount trend (is the curve steepening?).
- Integrate with the escalation rule (see `risk_escalation.md`) so CONSIDER_FORWARD
  also fires when the escalated risk level is HIGH.
