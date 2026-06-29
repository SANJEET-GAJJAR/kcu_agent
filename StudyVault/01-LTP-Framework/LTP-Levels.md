---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 3, kcu_framework.md
keywords: levels, failed reclaim, LTP level identification, key levels
---

# LTP Levels — Identification ★★★

#kcu #ltp #node

## Valid Level Types

| Level | Examples |
|-------|---------|
| Premarket | PM High, PM Low (drawn 4:30–9:30 EST) |
| Opening Range | OR High, OR Low (15-min range) |
| Opening Price | Day's opening price |
| Prior day | PDH, PDL |
| Hourly | Drawn ~8:30 EST, don't repaint intraday |
| Dynamite | SPX/SPY-specific, not generic TSLA |
| Intraday structure | HOD, LOD, VWAP |
| EMA/SMA | 8 EMA 5m, 21 EMA 5m, 200 SMA 2m/5m/1h/1D |
| Heatseeker nodes | Nodes that have proven themselves as S/R |

> [!warning]
> Price in the MIDDLE of a range = no level. Skip.

---

## ⚑ Failed Reclaim Level — Common Trap

> [!important]
> In a failed reclaim setup, the LEVEL is the **ceiling price couldn't get back above**.
> The PC forms BELOW the level — at the natural failure point.
> Do NOT require the PC to sit exactly AT the level.

```
Example (PLTR 2026-06-25):
- Price broke below Hourly 110.00
- Bounced to ~109.60 (did not reclaim 110)
- PC formed at ~109.13–109.63
- LEVEL = Hourly 110 (the failed ceiling)
- PC location = 109.50 (just below the failed level)
→ This IS a valid LTP setup. Level = ceiling, not where PC sits.
```

---

## Level Hierarchy (quality ranking)

```
A+ level: Fresh, untested, clean S/R, air on other side
A level: Tested once with clean reaction, holding structure
B level: Multiple tests, may be weakening
C level: Clustered with nearby levels, no clear magnet
NOT a level: middle of range, price in no-man's-land
```

---

## Hourly Levels — KCU Specifics

- Drawn fresh each day around **8:30 EST**
- Do not repaint during the day
- For backtesting prior days, use **TradingView Replay** (historical levels visible in replay)
- More levels become visible as price moves away from open

---

## "Sloppy Seconds" Rule

When price has ALREADY been delivered from a target node/level:
- Downgrade from A+ → B-/C+
- The node has already paid — expect diminished reaction on revisit
- Exception: node GROWS on second approach (may set up for gatekeeper break)

---

## Level + Heatseeker Node Conflict

When the nearest LTP structural level and the nearest Heatseeker node are at **different prices**:
- KCU structure > Heatseeker for entry/trend/setup decision
- But for PT1 target: if LTP level gives <0.5R and Heatseeker node gives ≥2R, use the Heatseeker node as PT1

→ See [[Integration-Framework]] for the full resolution rule.

## Related Notes
- [[LTP-Core]]
- [[LTP-Patience-Candle]]
- [[Rejection-Failed-Reclaim]]
- [[Common-Traps]]
