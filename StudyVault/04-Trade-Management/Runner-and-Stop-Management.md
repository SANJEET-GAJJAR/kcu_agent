---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 8, model audit trades 018/025
keywords: runner management, stop, breakeven, trail, fuel decay, stop management
---

# Runner & Stop Management ★★★

#management

## BE Stop Rule — Conditional, NOT Automatic

> The playbook says: "Take partial. Move stop to BE **only if reaction confirms**; otherwise trail below/above bounce/rejection candle wick."

| After PT1 hit | Condition met? | Action |
|---------------|----------------|--------|
| Price held bounce/rejection candle in trend direction ✓ | **Reaction confirms** | Move stop to BE |
| Price just barely pulled back, no reaction candle yet | **No confirmation yet** | Trail under the most recent bounce/rejection candle wick |

> [!warning]
> **Trade 018 / 025 pattern (documented miss):**
> PT1 hit → model says "move to BE matches the playbook" without checking if reaction confirmed.
> Result: flat BE stop gave back 4+ point gains for 0R.
> Fix: explicitly state WHICH branch of the conditional you're using at each PT1 decision.

---

## Oversized Candle Trail Rule

When any candle runs **≥2-3x the recent candle range** in your favor:
- This is an **immediate trail trigger** — move stop under that candle's structure (wick/midpoint)
- Do NOT leave a static stop (breakeven or otherwise) sitting through the full point range of the next bounce
- Applies whether or not PT1 partial has been taken

---

## Fuel-Decay Runner Exit Rule (CANDIDATE — 1 example)

Exit runner on the **FIRST** of these two signals:
1. The fueling -GEX node decays **≥50% off its peak magnitude**
2. King node **re-grows back toward or above its pre-break size**

> Both signals mean the cascade fuel is exhausted. Holding past this point = hope, not edge.

```
Trade 024 example (TSLA 2026-03-25):
  387.5 fuel node: -$15.2M peak → -$0.9M (94% decay)
  King 392.5: rebuilt to new high ($13.7M)
  Both signals at same time → exit at ~389.0-389.3 (~3.3R banked)
  Price later extended to 385.01 after a FRESH reload — that was a new trade, not the same runner
```

> [!important]
> Price extending FURTHER after a fuel-decay exit does NOT invalidate the exit rule.
> The fuel data was accurate. A fresh reload = fresh entry decision with its own PC.

---

## At-Spot Early Exit Rule (CANDIDATE — 1 example)

After entry, watch the node AT current spot (not King, not target node):
- If at-spot node was negative (cascade fuel) and flips toward POSITIVE within first 1-2 candles → **early invalidation signal**
- Don't wait for price to hit the hard stop — tighten immediately

```
Trade 028 example (TSLA 2026-03-27):
  Entry 09:38. At-spot node 365.0: -$3.4M at entry
  09:44: node flipped to +$75.2K (fully positive in 6 min)
  Stop ran at 09:44 — could have exited earlier when flip was clear
```

---

## Stop Placement Summary

| Entry type | Stop location |
|------------|--------------|
| LTP / PC-based | Other side of PC high/low |
| Rejection | Other side of rejected level/wick/node |
| At a psych/Hourly confluence | PC stop + bid/ask 5-second hold required |
| After ≥2-3x candle | Trail under that candle's structure |
| After fuel-decay signal | Exit — don't hold to stop |

## Related Notes
- [[Profit-Taking-Rules]]
- [[Cascade-Confirmation]]
- [[Invalidation-Rules]]
