---
source_pdf: TSLA_Setup_Invalidation_Library.md, TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: invalidation library
keywords: invalidation, early exit, fuel decay, polarity flip, node recency
---

# Invalidation Rules ★★★

#management #heatseeker

## Pre-Entry Invalidation Gates

### 1. R:R Gate (hard, non-negotiable)
- R:R < 1.5 = skip, regardless of signal quality
- If target is revised downward → recompute R:R against new target first
- If new R:R fails 1.5 = skip (not "take it smaller")

### 2. Node Recency Check (pre-entry)
Before entering on a large-node thesis:
- Check the node's trend over the **last 2-3 readings immediately before entry**
- "Node is huge" ≠ "node is still actively growing right now"
- If node peaked before entry and is easing = do not use size as confirmation

### 3. PA Freshness Check
- Is the entry a **fresh push** into the level?
- Or continuation after an already-partial rejection at the same zone?
- Continuation after partial rejection = weaker setup, grade down

---

## Live Invalidation (after entry)

### Fuel-Decay Exit (CANDIDATE — 1 example)
Exit when FIRST fires:
- Fueling -GEX node decays ≥50% off peak magnitude
- King node re-grows toward/above pre-break size

### At-Spot Polarity Flip (CANDIDATE — 1 example)
Exit/tighten when:
- At-spot node (the node AT current price, not King or target) flips polarity within 1-2 candles of entry
- Specifically: node was negative (cascade fuel) and crosses to positive = floor forming, cascade dead

> [!warning]
> This is FASTER than waiting for price to hit the hard stop. Check at 1-2 minute granularity.

### At Psych/Hourly Confluence (CANDIDATE — 1 example)
Additional requirement at round-number + Hourly Level confluences:
- Node polarity flip is necessary but NOT sufficient
- Must also have bid/ask 5-second hold beyond the level
- Without hold = wick-and-reclaim risk (Trade 033: entered on wick, reclaimed above 360)

---

## Post-Exit Invalidation (don't re-enter wrong)

- A position exiting at fuel-decay does NOT mean the original setup was wrong
- A fresh fuel reload (node reloads negative after decay) = **new entry** requiring its own PC/trigger
- Do NOT re-enter just because price kept moving — need independent setup confirmation

---

## Time-Based Invalidation

| Time | Grade impact |
|------|-------------|
| Before 9:45 AM | Lower quality — opening shuffle |
| 11:30–1:00 PM | Lower quality — lunch dead zone |
| After 3:00 PM | Avoid — stop trading reminder fires |
| After 3:00 PM (exceptional) | Grade down — require stronger confirmation |

## Related Notes
- [[Profit-Taking-Rules]]
- [[Runner-and-Stop-Management]]
- [[Cascade-Confirmation]]
- [[LTP-Core]]
