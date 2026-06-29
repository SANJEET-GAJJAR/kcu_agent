---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: all
keywords: quick reference, cheat sheet, KCU, LTP, Heatseeker
---

# KCU x Skylit Quick Reference

#dashboard #kcu #ltp #heatseeker

---

## Priority Stack → [[Integration-Framework]]

1. **Price action** — valid PC or rejection/reversal structure?
2. **KCU structure** — price at a real level, not the middle?
3. **R:R** — at least 1.5, prefer 2+?
4. **Market context** — SPY/QQQ, time of day, trend vs chop?
5. **Heatseeker/Atlas** — confirm, target, manage. Never replaces PA.

---

## LTP = Level + Trend + PC → [[LTP-Core]]

| Component | What it means |
|-----------|--------------|
| **Level** | Real level (PM H/L, OR H/L, Hourly, VWAP, PDH/L, major node). NOT middle of range. |
| **Trend** | 2m HH/HL (calls) or LL/LH (puts). VWAP side. EMA slope. |
| **PC** | Contained candle in trend direction. Break of PC = entry. PC ≠ trigger candle. |

**Failed reclaim level rule:** Level = the ceiling price COULDN'T reclaim. PC forms below the level. → [[LTP-Levels]]

---

## Patience Candle Exact Definition → [[LTP-Patience-Candle]]

- PC = candle **contained within prior candle's range** + in trend direction
- **Trigger candle = the candle whose break fires the entry. Trigger ≠ PC.**
- Bullish trigger: break above PC high. Bearish trigger: break below PC low.
- Stop: other side of PC. Entry: break of trigger.

---

## Node Types → [[Node-Taxonomy]]

| Node | Color | Behavior |
|------|-------|----------|
| +GEX / Yellow / Pika | Yellow | Stabilizer, sticky, magnet/target |
| -GEX / Purple / Barney | Purple | Accelerator, fuel, amplifies moves |
| **King** | Largest absolute | Daily anchor, gravity center |
| **Gatekeeper** | ≥1/4 King size | Obstacle between spot and King; fade 1st/2nd test |
| **Air Pocket** | Near-zero nodes | Fast movement zone |

**Magnitude > color always.** A -80M node > +20M node in importance. → [[Node-Taxonomy]]

---

## Node Direction Rule → [[Node-Direction-Rules]]

| Price approaching from | Node growing | Interpretation |
|------------------------|-------------|----------------|
| **Above** | +GEX growing | Ceiling / resistance |
| **Below** | +GEX growing | **Magnet / target — not a ceiling** |
| Either | Node draining as price approaches | Will pass through (being consumed) |
| Session extreme | -GEX node flips at low/high | Exhaustion signal, not regime change |

---

## Node Distance Framework → [[Node-Distance-Framework]]

| Distance from entry | Use |
|--------------------|-----|
| 0–2 pts | Critical — can block PT1 → reduce/skip |
| 2–4 pts | Valid PT1 / main target |
| 4–7 pts | PT2 / runner only |
| 7+ pts | Ignore for entry (unless King/macro) |

**Puts:** X-1 to X-2 = blockers · X-2.5 to X-4 = PT1  
**Calls:** X+1 to X+2 = blockers · X+2.5 to X+4 = PT1

---

## Heatseeker Role by Trade Type → [[Heatseeker-Entry-vs-Target]]

| Trade type | Heatseeker role |
|------------|----------------|
| Rejection / Reversal | **Primary** — node reaction IS the trade |
| LTP Trend Continuation | **Secondary** — targets/sizing only. LTP = go/no-go |
| Range / Whipsaw | **Primary at edges** only |
| Front-run | Risk control only |

**Rule: When LTP is A/A+, close Heatseeker for entry. Open it only for PT1, sizing, runner target.**

---

## Cascade Confirmation (3-of-3) → [[Cascade-Confirmation]]

All three required for stretch hold:
1. +GEX node **growing through the break**
2. Stacked negative nodes beneath
3. King **shrinking** (ceiling softening)

2-of-3 = scalp only at PT1. 1-of-3 = no stretch.

---

## PT Rules → [[Profit-Taking-Rules]]

| Situation | Rule |
|-----------|------|
| First large node hit | Take profit immediately — first touch usually reacts |
| Node breaks with acceptance + volume | Hold runner only |
| LTP PT1 hit | Take partial. Move stop to BE **only if reaction confirms**; otherwise trail wick |
| Gatekeeper ahead | Scale out, don't hold full size through it |
| Fuel node decays ≥50% + King rebuilds | Exit runner — cascade is over |

---

## Pre-Trade 7-Question Check → [[LTP-Core]]

1. Where is spot relative to major nodes?
2. If above node = support; if below = resistance
3. Is there a node that can pull price up/down?
4. Air pockets or few gatekeepers between here and target?
5. Has the target node already paid out this week? (If yes → downgrade)
6. Did price already test and return from entry node? (Sloppy seconds → B-/C+)
7. Which setup fits: LTP / Rejection / Reversal / No Trade?

---

## Scoring → [[LTP-Core]]

| Score | Grade |
|-------|-------|
| 9–10 | A+ / A — clean, repeatable, full size |
| 7–8 | B+ / B — valid with 1-2 weaknesses, normal/small size |
| 5–6 | C — mixed, scalp only |
| 1–4 | No trade |
