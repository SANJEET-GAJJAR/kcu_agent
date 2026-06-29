---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 3, kcu_framework.md PC section
keywords: patience candle, PC, trigger, contained, entry
---

# LTP Patience Candle — Exact Definition ★★★

#kcu #ltp

## ⚑ The Exact Definition (memorize)

> **PC = a candle CONTAINED WITHIN the prior candle's range AND in the direction of the move.**

- "Contained" = the PC's high and low are both within the prior candle's high and low (inside bar)
- "In the direction of the move" = for a downtrend short setup, a counter-color (green/bounce) candle that is contained counts as a failed-reclaim PC

> [!warning]
> **The TRIGGER candle is NOT the PC.** They are different candles.
> - PC = the contained candle
> - Trigger = the candle whose break fires the entry (the candle that breaks the PC's high or low)

---

## Entry Rules

| Direction | Entry trigger | Stop |
|-----------|--------------|------|
| **Bullish** | Break ABOVE PC high | Below PC low |
| **Bearish** | Break BELOW PC low | Above PC high |

```
Timeline example (bearish):
  Candle A (prior): High 110.50, Low 109.80
  Candle B (PC):    High 110.20, Low 109.90  ← CONTAINED within A
  Candle C (entry): Breaks below 109.90      ← This is the TRIGGER, not the PC
  Entry: ~109.85 (just below PC low)
  Stop: 110.25 (just above PC high)
```

---

## PC Quality Factors

| Factor | Good PC | Bad PC |
|--------|---------|--------|
| Range | Small (tight) | Large (wide) |
| Location | At or near a level | Floating in middle |
| Containment | Clearly inside prior candle | Ambiguous / barely inside |
| Direction | Matches trend | Contradicts trend |
| Pullback volume | Lower than prior candles | Higher (aggressive against trend) |

> [!tip]
> If PC candle is unclear → ASK "Which candle is the PC?" Do not guess. Do not analyze an ambiguous PC.

---

## PC Filters (KCU Indicator)

The LTP Indicator can filter PCs by:
- Auto Fibonacci (50% reclaim = continuation, 59% break = reversal)
- Volume (lower than prior candle)
- VWAP / EMA (bullish PCs above, bearish below)
- NTZ / Opening Range / Premarket Range

> [!warning]
> Filters reduce noise but can hide valid entries. A filtered PC that conflicts with clear PA → explain the conflict, don't auto-skip.

---

## PC Arrow Colors (KCU Indicator)

| Color | Meaning |
|-------|---------|
| Yellow ▽ / △ | Current/latest patience candle forming |
| Green ▲ | Possible bullish triggered PC entry |
| Red ▽ | Possible bearish triggered PC entry |
| Purple | All PCs (triggered or not) — study/backtest only |

---

## 30-Second Rule

If enabled: PC visual/alert appears only in the **last 30 seconds** before candle close.
- This is a WARNING that a PC may form — NOT permission to enter early
- If disabled: alert triggers only after PC is confirmed

---

## When to Skip the PC

- PC is unclear or ambiguous → ask before grading
- PC range is too large relative to stop size → stop too wide, R:R fails
- PC formed AFTER the same setup already failed once today → don't retry
- Price is approaching 200 SMA without enough room to PT1

## Related Notes
- [[LTP-Core]]
- [[LTP-Levels]]
- [[Rejection-Failed-Reclaim]]
