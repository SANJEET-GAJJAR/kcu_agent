---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: sections 3, 18
keywords: practice, LTP, levels, trend, patience candle
---

# LTP Framework Practice (10 questions)

#practice #ltp

## Related Concepts
- [[LTP-Core]] · [[LTP-Levels]] · [[LTP-Patience-Candle]]

> [!hint]- Key Patterns
> | Keyword | Answer |
> |---------|--------|
> | LTP components | Level + Trend + Patience Candle (all 3 required) |
> | PC vs trigger | PC = contained candle. Trigger = the candle whose break fires the entry. They are DIFFERENT candles. |
> | Failed reclaim level | The CEILING price couldn't get back above — not where the PC sits |
> | R:R minimum | 1.5 hard gate — skip regardless of signal quality |
> | After PT1 — stop to BE | Only if reaction confirms. Otherwise trail the wick. |

---

## Q1 — LTP Definition [recall]
> What does LTP stand for, and what is the required order?

> [!answer]- Answer
> **L**evels, **T**rend, **P**atience Candle. All three required, checked in this order: Level first (is price at a real level?), Trend second (is direction clear?), PC third (is there a contained entry trigger?). Partial LTP is dangerous.

---

## Q2 — PC vs Trigger [recall]
> A trader says "the PC triggered at 9:37." What does this actually mean? What is the PC and what is the trigger?

> [!answer]- Answer
> The **PC** (patience candle) is the **contained candle** — a candle whose high and low are both inside the prior candle's range, in the direction of the move. The **trigger** is the candle that BREAKS the PC's high (bullish) or low (bearish). "PC triggered" means the trigger candle's break fired the entry — NOT that the PC is the trigger candle. These are different candles.

---

## Q3 — Failed Reclaim Level [application]
> TSLA breaks below Hourly 390. Price bounces to 389.60 but can't close above 390. A contained green candle forms at 389.30–389.60. What is the "L" in the LTP setup? Where is the stop?

> [!answer]- Answer
> The **level = Hourly 390** (the ceiling price could NOT reclaim). The PC is at 389.30-389.60 (just below the level). Entry: break below PC low (~389.30). Stop: above PC high (~389.65). The level is the ceiling above the PC — not where the PC sits. This is a failed reclaim short.

---

## Q4 — R:R Gate [application]
> A bearish LTP setup: entry 392.00, stop 392.60 (0.60 pt risk), PC failed reclaim. Heatseeker says the nearest floor is at 393.00 (first positive node). What is the R:R and what's the correct action?

> [!answer]- Answer
> PT1 = 393.00... wait, that's ABOVE entry (392.00) for a SHORT. This would mean the target is the wrong direction — there's no valid PT1 below entry. R:R cannot be calculated. This is a no-trade: no valid downside target within range. Alternatively if the question means the nearest downside node is 390.40 (2.20R from entry of 392.60 stop vs 1.60 R target) = 2.67R → trade valid if verified.

---

## Q5 — Timeframe Convention [recall]
> What timeframe should be used for entries/triggers at 9:42 AM? At 10:15 AM? At 11:30 AM?

> [!answer]- Answer
> - 9:42 AM: **2-minute chart** (early session, before 10 AM)
> - 10:15 AM: **5-minute chart** (primary after 10 AM)
> - 11:30 AM: **5-minute chart** (still primary, or 10m for broader context after 11 AM). The 2-minute is for confluence stacking, not the actual break level.

---

## Q6 — Skip Conditions [recall]
> Name 5 hard skip conditions that override a good-looking PC setup.

> [!answer]- Answer
> Any 5 of: (1) No clean level; (2) No clean trend; (3) PC too large / ambiguous; (4) Clustered levels (no clean target); (5) R:R < 1.5; (6) Approaching 200 SMA without room to PT1; (7) Price in middle of range; (8) Same PC/setup already failed today; (9) PT1 blocked by opposing node within 0-2 pts.

---

## Q7 — Priority Stack [recall]
> Rank the 5 elements of the KCU priority stack in order. What is Heatseeker's position?

> [!answer]- Answer
> 1. Price action (valid PC or rejection/reversal structure) 2. KCU structure (price at a real level, not middle) 3. R:R (≥1.5, prefer 2+) 4. Market context (SPY/QQQ, time of day) 5. **Heatseeker/Atlas** (confirm, target, manage — never replaces #1-2). Heatseeker is #5 — it does not gate LTP entries.

---

## Q8 — Grade & Size [application]
> A TSLA setup: clean trend, good PC, at OR Low, R:R = 2.1, Heatseeker 2-of-3 cascade confirmed. What grade and size?

> [!answer]- Answer
> KCU grade: **A** (clean level, trend, PC, R:R ≥2). Heatseeker: 2-of-3 = not full cascade. Per sizing matrix: A + 2-of-3 = **Half size**. Do not use full size without 3-of-3 cascade confirmation. PT1 scalp first, extend only if third confirmation fires in real time.

---

## Q9 — Sloppy Seconds [recall]
> What is "sloppy seconds" in KCU context and how does it affect grade?

> [!answer]- Answer
> "Sloppy seconds" = attempting an entry at a level/node that has ALREADY been tested and reacted once this session. The first touch of a level gets A+/A treatment. The second touch (after the level already "paid out") is downgraded to B-/C+. The node has been visited; diminished reaction expected. Exception: if the node GREW on the second approach, it may set up a gatekeeper break.

---

## Q10 — Failed LTP Watch [recall]
> What action is taken when an LTP entry fails to make the expected HH/HL? What is NOT allowed?

> [!answer]- Answer
> Tag as **FAILED_LTP_WATCH**. Do NOT retry the same direction immediately. Do NOT flip to the opposite direction as a "Failed LTP entry." Wait for a FRESH confirmed setup (new PC, new level, new trend context). **FAILED_LTP_ENTRY is not an allowed strategy** — it is a warning/journal tag only.
