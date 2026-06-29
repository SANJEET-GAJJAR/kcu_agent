---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 7J, 9, kcu_framework.md NTZ
keywords: no trade, NTZ, skip, avoid, chop, rainbow road
---

# No-Trade Conditions ★★★

#setup #ltp

> [!important]
> Default to no-trade over forced trade. Log good skips — they are as valuable as winning entries.

---

## Hard No-Trade Conditions

| Condition | Why |
|-----------|-----|
| No valid PC and no clear rejection/reversal trigger | No entry signal |
| PT1 blocked by opposing node within 0-2 pts | R:R fails before you even enter |
| Rainbow Road — many conflicting nodes | No structural dominance |
| Price in middle of range / no-man's-land | No level = no trade |
| R:R < 1.5 | Hard gate — skip regardless of signal quality |
| Heatseeker and PA conflicting, both unclear | Wait for clarity |
| Same PC/setup already failed once today | Do not retry |

---

## Time-Based No-Trade / Lower Quality Zones

| Time | Quality |
|------|---------|
| Before 9:45 AM | **Lower quality** — opening shuffle, spread, whipsaw |
| 9:45–10:00 | Opening shuffle clearing — improving |
| 10:00–11:20 | **Prime time** — best setups |
| 11:20–1:00 PM | **Lunch dead zone** — avoid or scalp only |
| 1:00–3:00 PM | **Afternoon reset** — re-evaluate fresh map |
| 3:00–3:30 PM | Power hour — gamma intensifies |
| 3:30–4:00 PM | Unwind/liquidation — rapid moves, fakeouts — avoid |
| After 3:00 PM | Stop trading reminder fires on KCU indicator |

---

## "Sloppy Seconds" No-Trade

A setup where price has already been DELIVERED to the target node/level this session:
- First touch of a level = A+/A
- Second touch (already paid out) = B-/C+ at best
- If node was fully consumed (drained to near zero) on first visit → skip the second approach

---

## Session Discipline Rules

- Maximum 2-3 quality setups per session
- If profitable in the morning → reset until after lunch unless a new A+ appears
- After a massive winner → take a 20-minute break
- Never average down on a loser. Scale into winners only after confirmation.
- "If you are worried about theta, you are sized too large."

---

## Good Skip Examples

- **Trade 005** (TSLA 2026-06-18): B technical / No Trade correct. VWAP/EMA rejection short — setup technically valid but spread cost would eat the ~$1 target. Correct skip on cost basis. → [[Rejection-Failed-Reclaim]]
- **Trade 014** (TSLA 2026-06-17): Correct no trade — VWAP reclaim PA invalidated before entry. Heatseeker and PA agreed: King sitting AT contested level (not below it), no breakout support.
- **Trade 026** (TSLA 2026-03-26): Correct skip — R:R gate failed (R:R ≈ 1.0 on capped target). Signal quality was good but gate is non-negotiable.

## Related Notes
- [[LTP-Core]]
- [[Node-Distance-Framework]]
- [[Invalidation-Rules]]
