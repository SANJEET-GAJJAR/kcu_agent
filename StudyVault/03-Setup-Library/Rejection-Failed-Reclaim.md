---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 7B-C, kcu_framework.md
keywords: rejection, failed reclaim, failed breakdown, VWAP rejection, PC
---

# Rejection & Failed Reclaim ★★★

#setup #ltp

## Rejection Play

**Best when:** Price tests a major level/wall/node, fails to hold/reclaim, gives a small-risk entry away from the rejected level.

| Component | Rule |
|-----------|------|
| Entry | Rejection wick, failed reclaim, PC break AWAY from the level |
| Stop | Other side of the rejected level/wall/HOD/LOD/PC |
| PT1 | Nearest opposite node or LTP level |

**A+ conditions:** fresh level, strong wall/node at the rejection, open air to target, trend/context agrees, clear R:R, PC confirms.

**Skip if:** choppy, market against thesis, no clear level, blocking level ahead, poor trend, weak volume, PC unclear.

---

## ⚑ Failed Reclaim (Short) — Level Identification

> **The LEVEL is the ceiling price could NOT get back above.**
> **The PC forms BELOW the level** at the natural failure point.

```
Sequence:
  1. Price breaks below a key level (OR Low, Hourly, VWAP)
  2. Price bounces back toward the level
  3. Bounce FAILS to reclaim — candle closes below the level
  4. Contained PC forms just below the level
  5. Entry: break below PC low
  6. Level: the ceiling above, not where the PC sits
```

**Trade examples:**
- **Trade 001** (TSLA 2026-06-18): A- failed reclaim short at PDL 393.76/OR-Low. PC contained inside bar. Win.
- **PLTR trade** (2026-06-25): A+ failed reclaim of Hourly 110. PC at 109.13-109.63. Model initially missed the level.

---

## Failed Breakdown (Long)

Opposite of failed reclaim:
- Price breaks BELOW a key level
- Snaps back ABOVE and holds reclaim
- PC forms above the level (reclaim candle contained)
- Entry: break above PC high
- Target: next resistance level above

---

## VWAP Rejection

Heatseeker weight: **Primary** (local VWAP reaction IS the trade).

- Price comes from below VWAP (Advanced VWAP) or above (rejection)
- PC closes above VWAP (bullish) or rejects at VWAP from above (bearish)
- Entry: next candle after PC

**Contradiction in KCU training:** Advanced VWAP — some notes say needs trend, some say works in chop.
Working interpretation: Do not use in random chop. Best in controlled pullback/reclaim with PC and room to target.

---

## OR Low / OR High Rejection

- ORB (15-minute Opening Range Breakout) levels act as key S/R
- Break and return into range = chop/failed breakout
- Break and hold = trend direction confirmed
- PC at ORB retest: entry uses PC logic, stop PC-based

**Trade examples:**
- **Trade 004** (TSLA 2026-06-18): B+ rejection at OR Low (fresh level, 8 EMA confluence). Win 3.33R.
- **Trade 023** (TSLA 2026-03-25): A-/A rejection at 200 SMA daily / OR High confluence. Heatseeker node flip led by 1-2 min.

## Related Notes
- [[LTP-Core]]
- [[LTP-Levels]]
- [[LTP-Patience-Candle]]
- [[Heatseeker-Entry-vs-Target]]
