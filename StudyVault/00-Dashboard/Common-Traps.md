---
keywords: exam traps, common mistakes, model audit
---

# Common Traps & Model Misses

#dashboard #model-audit

> [!warning] Purpose
> Mistakes that have actually happened in live sessions — documented to prevent repetition.

---

## LTP Entry Traps

> [!danger]- Trap: Using Heatseeker to second-guess a clean LTP entry
> - **What happens**: A/A+ LTP setup exists (Level + Trend + PC confirmed). Heatseeker node oscillation at entry is consulted and interpreted as "momentum slowing" → entry graded down to B-.
> - **Why it's wrong**: Heatseeker is for targets/sizing AFTER LTP says go. It is NOT a gate on LTP entries. This inverts the priority stack.
> - **Correct approach**: Make the go/no-go with LTP only. Then open Heatseeker for PT1 + sizing.
> - [[Integration-Framework]] · [[Heatseeker-Entry-vs-Target]]

> [!danger]- Trap: Failed reclaim level — requiring the PC to sit AT the level
> - **What happens**: Price breaks below a level (e.g., Hourly 110), bounces but fails to reclaim. PC forms just below the level. Model calls "no clean level" because the PC isn't AT the level.
> - **Why it's wrong**: In a failed reclaim, the LEVEL is the ceiling price couldn't get back above. PC forms at the natural failure point BELOW the level — that IS the LTP setup.
> - **Correct approach**: Level = ceiling above the PC. Not where the PC sits.
> - [[LTP-Levels]]

> [!danger]- Trap: Calling a valid trend-pullback PC "late" or "momentum chase"
> - **What happens**: A vertical cascade already happened. PC forms at a level with tight invalidation in trend direction. Model dismisses as "momentum chase."
> - **Why it's wrong**: A trend-based trader enters PULLBACKS. If the PC exists at a level with tight invalidation, grade it — don't dismiss based on velocity context.
> - [[LTP-Trend-Pullback]]

---

## Heatseeker Node Traps

> [!danger]- Trap: Growing positive node from below = ceiling
> - **What happens**: Positive node triples as price bounces from below toward it. Model calls "rejection incoming at this node."
> - **Why it's wrong**: A growing positive node with price below it = MAGNET/TARGET pulling price toward it, not a ceiling above it.
> - **Correct approach**: Same node, opposite implication depending on which side price is approaching from.
> - [[Node-Direction-Rules]]

> [!danger]- Trap: Massive negative node = guaranteed pass-through
> - **What happens**: Large -GEX node below price (-$8M+). Model calls "fuel, price will blow through it."
> - **Why it's wrong**: When a negative node is KING-level magnitude AND at a structural confluence (Hourly + round number), it is also a violent reaction zone. Magnitude > color.
> - [[Node-Taxonomy]] · [[Node-Direction-Rules]]

> [!danger]- Trap: Node size = node still growing NOW
> - **What happens**: Large node (-$44M) at entry target. Model calls "strong confirmation."
> - **Why it's wrong**: "This node is huge" ≠ "this node is still actively growing right now." Node may have peaked 3 min before entry and already be easing. Check the last 2-3 readings.
> - [[Node-Taxonomy]]

> [!danger]- Trap: Node polarity flip at psych/Hourly level = confirmed break
> - **What happens**: At-spot node flips negative at a round-number + Hourly confluence. Model says "level broken, entry valid."
> - **Why it's wrong**: Round-number + Hourly confluences produce stop-run wicks. Flip is necessary but NOT sufficient — also need bid/ask 5-second hold.
> - [[Invalidation-Rules]]

> [!danger]- Trap: Negative node flip at session extreme = bearish regime
> - **What happens**: At the cascade low, a positive node briefly flips negative. Model reads this as continued bearish pressure.
> - **Why it's wrong**: Negative flip at session extreme = temporary exhaustion of floor energy. When it flips back positive = bounce confirmed.
> - [[Node-Direction-Rules]]

---

## Management Traps

> [!danger]- Trap: Flat BE stop after oversized candle
> - **What happens**: Trade moves 4+ pts in favor. Model leaves stop at flat breakeven. Next normal bounce runs the stop for 0R.
> - **Why it's wrong**: Any candle running ≥2-3x the recent candle range = immediate trigger to trail under that candle's structure. Do not leave static stop through a full normal bounce.
> - [[Runner-and-Stop-Management]]

> [!danger]- Trap: Moving stop to BE without confirming "reaction confirms"
> - **What happens**: PT1 hit on LTP trend trade. Model says "move to breakeven — matches playbook."
> - **Why it's wrong**: The playbook rule is conditional: move to BE *only if reaction confirms*. Otherwise trail below/above the bounce/rejection candle wick.
> - [[Runner-and-Stop-Management]]

> [!danger]- Trap: Capping target when node data justifies lower target, without re-running R:R
> - **What happens**: Heatseeker justifies lower PT1. Model recommends the capped target. R:R is never re-computed against the new target.
> - **Why it's wrong**: When a target is revised downward, re-run the R:R gate against the NEW target. If it fails 1.5, it's a skip — not a "take it smaller."
> - [[Profit-Taking-Rules]]

> [!danger]- Trap: King shrinkage = distance decay confused with reversal signal
> - **What happens**: King node declines from peak after price moves away from it. Model flags as reversal signal.
> - **Why it's wrong**: King declining as price MOVES AWAY from it = distance decay. King declining as price is NEAR it = deceleration/reversal. Different readings.
> - [[Node-Taxonomy]]
