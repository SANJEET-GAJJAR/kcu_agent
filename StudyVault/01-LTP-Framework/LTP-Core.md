---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: sections 3, 18
keywords: LTP, levels, trend, patience candle, priority stack
---

# LTP Framework — Core ★★★

#kcu #ltp

## Overview Table

| Component | Role | Gate order |
|-----------|------|-----------|
| **L — Level** | Where price is (real level, not middle) | 1st |
| **T — Trend** | Direction (2m/5m HH/HL or LL/LH) | 2nd |
| **P — Patience Candle** | Entry trigger (contained + in-trend) | 3rd |

> [!important]
> All three required. Partial LTP is dangerous. Order matters — check L first, then T, then P.

---

## Priority Stack (memorize this)

```
1. Price action       ← valid PC or rejection/reversal structure?
2. KCU structure      ← price at a real level, not the middle?
3. R:R                ← ≥1.5 minimum, prefer 2+
4. Market context     ← SPY/QQQ, time of day, trend vs chop
5. Heatseeker/Atlas   ← confirm target/manage. NEVER replaces #1-2
```

> [!warning]
> Heatseeker is #5. It does NOT gate entry when 1-4 are aligned. LTP = go/no-go for continuation setups.

---

## Grading Scale

| Score | Grade | Size |
|-------|-------|------|
| 9–10 | A+ / A | Full size (if RR≥2, entry near invalidation, context supports) |
| 7–8 | B+ / B | Half / normal size |
| 5–6 | C | Scalp only |
| 1–4 | No trade | — |

---

## Hard R:R Gate

- **Minimum R:R = 1.5 or skip — regardless of signal quality**
- Stop ≥ previous candle range
- If PT1 is wrong/mis-set at a node, **retarget first**, then re-test the gate
- If Heatseeker justifies a LOWER target → recompute R:R against the new target. If it fails 1.5 = SKIP

---

## Pre-Trade 7-Question Check

1. Where is spot relative to major nodes?
2. If above node = look for support; if below = look for resistance
3. Is there a node that can pull price up/down?
4. Air pockets or few gatekeepers between spot and target?
5. Has target node already paid out this week? (Yes = downgrade to B-/C+)
6. Is the entry near sloppy-seconds territory? (Second test of same setup = degrade)
7. Which setup applies: LTP / Rejection / Reversal / No Trade?

---

## Supported Timeframes (KCU indicator)

- **2m**: early session (pre-10:00 AM)
- **5m**: after 10:00 AM (primary for entries/triggers)
- **10m**: after 11:00 AM for broader context
- **1h / 1D**: level identification only, not triggers
- Stop trading reminder fires at **15:00 EST**

---

## Skip Conditions (hard)

- No clean level
- No clean trend
- PC unclear / too large / ambiguous
- Levels too close together (clustered)
- Poor R:R
- Approaching 200 SMA without room
- Price in middle of range
- Same PC/setup already failed once today

## Related Notes
- [[LTP-Levels]]
- [[LTP-Patience-Candle]]
- [[Integration-Framework]]
- [[Common-Traps]]
