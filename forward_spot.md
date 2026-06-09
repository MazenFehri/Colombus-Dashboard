# Spot vs. Forward Recommendation — Design Options

> Working notes for the "should the business use spot or forward?" feature.
> Documents the concept, the data constraint, the business perspective, and the
> three candidate approaches with trade-offs. No decision is locked in yet.

---

## 1. Concept: what "spot" and "forward" mean here

| Term | Meaning | When you'd want it |
|------|---------|--------------------|
| **Spot** | Buy/sell the currency **now** at today's rate, settle immediately (T+2). | You need the currency now, or you expect the rate to move in your favour. |
| **Forward** | **Lock today's agreed rate now**, but settle on a **future date** (e.g. 1M / 3M / 6M). | You have a known future payment/receipt and want certainty — protection against the rate moving against you. |

A forward removes uncertainty: you know exactly what rate you'll get. The cost of that certainty is that you can't benefit if the rate later moves in your favour.

---

## 2. The data constraint (important)

Our only data source is **Frankfurter v2**, which provides **spot rates only**.

A *true* forward rate is not a prediction — it is derived from the **interest-rate differential** between the two currencies (covered interest parity):

```
Forward = Spot × (1 + r_quote × t) / (1 + r_base × t)
```

where `r_quote` / `r_base` are the two currencies' interest rates and `t` is the time to settlement in years.

**We do not currently have interest-rate data.** So out of the box we can:
- ✅ Show historical & current **spot** rates, trend, volatility, risk.
- ❌ **Not** quote an accurate forward price — unless we add an interest-rate source.

This constraint is what separates the three options below.

---

## 3. Business perspective (affects every option)

The recommendation **flips depending on the exposure direction**:

| Business type | Exposure | Hurt when… | Forward helps when… |
|---------------|----------|------------|---------------------|
| **Importer** (will **buy** foreign currency later) | Pays in foreign currency | The foreign currency **rises** | Rate is trending **up** / volatile |
| **Exporter** (will **receive** foreign currency later) | Earns foreign currency | The foreign currency **falls** | Rate is trending **down** / volatile |

→ The UI needs the user to pick their side (Importer / Exporter), or it must show both. Without this, "spot or forward" has no single correct answer.

---

## 4. The three options

### Option A — Heuristic signal from our own data  *(no new data needed)*

Recommend spot or forward from the **trend + volatility + risk** we already compute, combined with the user's exposure direction. Clearly labelled as **guidance, not a price quote**.

**Logic sketch:**
```
if rate trending AGAINST the user  AND  volatility elevated:
    → CONSIDER FORWARD (lock today's level)
elif rate trending IN FAVOUR  AND  volatility low:
    → SPOT IS REASONABLE (you may benefit by waiting)
else:
    → NEUTRAL (no strong signal)
```

**Example output:**
```
Recommendation: CONSIDER FORWARD
Why: EUR/TND is trending up (+1.8% / 30d) and volatility is elevated.
If you must BUY euros later, locking today reduces the risk of paying more.
(Educational guidance — not a price quote)
```

- **Pros:** Uses data we already have; deterministic; explainable; ships fast.
- **Cons:** Not an actual forward price; it's directional decision-support, not a quote.
- **Data needed:** None.

---

### Option B — Compute a real forward rate  *(needs interest-rate data)*

Add interest rates for TND, USD, EUR and compute the forward via covered interest parity, for standard tenors (1M / 3M / 6M).

**Example output:**
```
Forward (3M) = Spot × (1 + r_q·t) / (1 + r_b·t)
Spot EUR/TND      3.3761
3M forward (est)  3.4012  (+0.74%)
```

- **Pros:** Financially "correct"; shows the actual forward premium/discount; genuinely useful for hedging decisions.
- **Cons:** Requires a **reliable interest-rate source** (esp. TND money-market rates, which are harder to source than EUR/USD); more moving parts; rates must be kept current.
- **Data needed:** Short-term interest rates per currency (new external source or manual config).

---

### Option C — Let the AI explain it  *(narrative, no new data)*

Feed the selected date's trend / volatility / risk (and exposure direction) into the existing AI commentary and let it narrate whether spot or forward looks preferable, in plain language.

**Example output:**
```
"With EUR/TND drifting higher and recent swings widening, an importer buying
euros may prefer a forward to lock today's level; an exporter has less urgency
and could stay on spot."
```

- **Pros:** Flexible, human-readable, reuses the existing AI pipeline; good at explaining *why*.
- **Cons:** Non-deterministic; no hard number; quality depends on the model; harder to test.
- **Data needed:** None (reuses current AI commentary).

---

## 5. Comparison at a glance

| | A. Heuristic | B. Real forward | C. AI narrative |
|---|---|---|---|
| New data source | None | Interest rates | None |
| Output type | Signal + reason | Actual forward price | Plain-language advice |
| Deterministic / testable | Yes | Yes | No |
| Financial accuracy | Directional only | High | Directional only |
| Effort | Low | Medium–High | Low |
| Needs exposure direction | Yes | For advice, yes | Yes |

---

## 6. Possible combination

These aren't mutually exclusive. A natural staged path:

1. **Start with A** (heuristic signal) — ships now, no new data.
2. **Layer C** on top — AI explains the signal in business terms.
3. **Upgrade to B** later — if/when a trustworthy interest-rate source is wired in, replace the heuristic's "forward" leg with a real computed forward price.

---

## 7. Open questions to resolve before building

- Which option (or combination) do we want for v1?
- Should the user **select Importer vs Exporter**, or do we show **both** sides?
- For Option B: is there an acceptable interest-rate source (incl. TND), or do we treat rates as manually-configured constants?
- Does this live as a **new panel** on the dashboard, tied to the **calendar-selected date**, or as part of the existing Market Intelligence card?
