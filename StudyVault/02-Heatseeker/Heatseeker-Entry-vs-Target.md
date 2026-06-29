---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: sections 4, 6, PLTR/NVDA model audit 2026-06-25
keywords: Heatseeker role, entry domain, target selection, LTP vs Heatseeker
---

# Heatseeker — Entry vs Target Use ★★★

#heatseeker #integration

## ⚑ The Hard Rule

> **For LTP continuation setups: close Heatseeker for the entry decision. Open it only AFTER LTP says go.**
> Heatseeker at LTP entries = noise. Heatseeker for targets/sizing = essential.

---

## Heatseeker Role by Trade Type

| Trade type | Heatseeker role | Primary decision-maker |
|------------|----------------|----------------------|
| **Rejection / Reversal** | **Primary** — node reaction IS the trade | Heatseeker (node is the level) |
| **LTP Trend Continuation** | **Secondary** — targets/sizing only | LTP (trend + PC = go/no-go) |
| **LTP Failed Reclaim** | **Secondary** — targets/sizing only | LTP |
| **Range / Whipsaw** | **Primary at edges** | Heatseeker + PA at edge levels |
| **Front-run** | **Risk control only** | LTP (very small if taken) |

---

## Two-Stage Process for LTP Trades

```
STAGE 1 — Entry Decision (LTP only):
  Level present? ✓
  Trend confirmed? ✓
  PC clean? ✓
  R:R ≥ 1.5? ✓
  → GO
  
STAGE 2 — After entry confirmed (Heatseeker):
  What is PT1? → Next positive floor or nearest fuel zone
  What size? → Cascade fuel growing = fuller size; positive nodes stacking below = scalp
  Where is runner target? → Next major node beyond PT1
  What invalidates? → King rebuilding, fuel draining, floor strengthening
```

---

## When Heatseeker IS Valid at Entry (exceptions)

Two cases where Heatseeker IS the entry reason:

1. **Pure King Node Rejection**: massive King node just above price, price opens/approaches from below → King is both the level AND the entry reason. Heatseeker IS primary here.

2. **Gatekeeper Fade**: large gatekeeper node between spot and King on 1st/2nd test → Heatseeker node is the entry level. PC still required for trigger.

In both cases: the node IS the structural level. This is different from LTP where the level is a price-action structure (PM High, OR Low, etc.)

---

## What Heatseeker CANNOT Do (confirmed gaps)

| Gap | Explanation |
|-----|-------------|
| Cannot gate LTP entries | Inverts priority stack — causes grade inflation of bad setups or deflation of good ones |
| Cannot predict exact reversal tick | Gives 1-4 min lead time before actual extreme — use as warning, not precision exit |
| Cannot override exhaustion | A massive negative node is a TARGET, not a guarantee of arrival |
| Cannot resolve node vs PA level conflict alone | See [[Integration-Framework]] |

---

## Heatseeker for Management (correct use)

After entry, Heatseeker's job:

1. **PT1**: Find the next positive floor (for puts) or negative fuel (for calls) within 2-4 pts
2. **Runner hold/exit**: Is cascade fuel still growing? King still shrinking? → Hold. Fuel draining 50%+ + King rebuilding → Exit runner
3. **Early invalidation**: At-spot node flips polarity in first 1-2 candles after entry → tighten/exit before stop is hit
4. **Re-entry**: Did fuel node reload after exit? → Fresh PC needed, re-grade independently

## Related Notes
- [[Integration-Framework]]
- [[Node-Direction-Rules]]
- [[Cascade-Confirmation]]
- [[Common-Traps]]
