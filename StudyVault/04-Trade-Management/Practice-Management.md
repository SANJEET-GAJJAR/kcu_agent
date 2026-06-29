---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf, TSLA_Model_Audit.md
part: section 8, model audit
keywords: practice, management, PT1, runner, stop, fuel decay
---

# Trade Management Practice (10 questions)

#practice #management

## Related Concepts
- [[Profit-Taking-Rules]] · [[Runner-and-Stop-Management]] · [[Cascade-Confirmation]] · [[Invalidation-Rules]]

---

## Q1 — PT1 Rule [recall]
> When the first large Heatseeker node is hit, what is the immediate action?

> [!answer]- Answer
> **Take profit immediately.** First touch of a large node almost always reacts. Do not hold full size through the first node touch. Scale out (take most/all profit). Only hold a runner if node breaks WITH acceptance AND volume continues AND cascade 3-of-3 is still confirmed.

---

## Q2 — BE Stop Condition [application]
> PT1 is hit on an LTP trend trade. Price is 393.80 at PT1, then pulls back to 394.20 without printing a reaction candle. Should stop be moved to breakeven?

> [!answer]- Answer
> **No.** The playbook rule is: "Move stop to BE *only if reaction confirms*." A reaction candle means a bounce/rejection candle in the trend direction that confirms the move is holding. If price pulled back to 394.20 without printing such a candle, reaction has NOT confirmed. Correct action: **trail the stop under the most recent bounce/rejection candle wick** — not flat breakeven.

---

## Q3 — Fuel Decay Exit [application]
> Runner held on puts. At 12:16, fuel node 387.5 = -$15.2M (peak). By 12:34: fuel node = -$0.9M (94% decay). King rebuilt from $8.2M to $13.7M (new high). What is the correct action?

> [!answer]- Answer
> **Exit the runner.** Both fuel-decay exit conditions fired: (1) Fuel node decayed ≥50% off peak (94% → well past threshold); (2) King rebuilt to a new high (ceiling re-asserting). These signal the cascade is out of fuel. Continuing to hold = hope, not edge. Exit at the next reasonable price (~389.0-389.3 in the real example). If price later extends on a fresh fuel reload, that is a **new, separate entry** — not a reason to have held the original runner.

---

## Q4 — Oversized Candle Trail [application]
> Recent candle range: ~1.1 pts. A single cascade candle drops 4.0 pts in your favor. Price bounces back 1.3 pts on the next candle. You have a static BE stop. What happened and what should have happened?

> [!answer]- Answer
> **What happened**: the 4.0 pt candle (3.6x recent range) triggered the oversized candle trail rule — immediate trigger to trail stop under that candle's structure. A static BE stop sitting through a 1.3 pt bounce got hit for 0R. **What should have happened**: as soon as the 4 pt candle closed, trail the stop to just above its high (for shorts) or below its low (for longs). The entire gain would not have been given back.

---

## Q5 — At-Spot Flip [application]
> Entry on puts at 364.20 (stop 365.98). At 09:34 the at-spot node 365.0 = -$3.4M. At 09:40 = -$1.4M. At 09:44 = +$75.2K (flipped positive). Stop not yet hit. What action?

> [!answer]- Answer
> **Tighten immediately / exit.** The at-spot node (the node AT current price) flipped from negative (cascade fuel) to positive (floor forming) within 6 minutes of entry. This is the at-spot polarity flip early invalidation signal — faster than waiting for price to tag the hard stop. The floor is forming under price, meaning the cascade thesis is dead. Exit or tighten to near-zero risk. Don't wait for the 365.98 stop to run.

---

## Q6 — Cascade Sizing [recall]
> LTP grade = A. Heatseeker cascade check: +GEX grew through the break ✓. Stacked -GEX below ✓. King flat (not shrinking) ✗. What size?

> [!answer]- Answer
> **2-of-3 cascade = half size, scalp to PT1 only.** King is flat (not shrinking) which means the ceiling is not actively softening. Without King shrinking, the pull-back pressure remains — a flat King tends to pull price back toward it once the initial move stalls. Take PT1 and exit. Do not hold for a stretch runner with 2-of-3 only.

---

## Q7 — Gatekeeper Management [recall]
> Price is approaching a gatekeeper node for the THIRD time. You are holding a long runner. What is the correct action?

> [!answer]- Answer
> **Scale out / take significant profit.** On the first and second test of a gatekeeper, fade (the gatekeeper tends to hold). On the **third test**, the probability shifts toward the gatekeeper BREAKING — but this is not a time to hold full size. Scale out as price approaches: take most profit and hold only a small runner. If the gatekeeper absorbs (price fails to break), exit the rest. If it breaks with acceptance, re-evaluate for a fresh entry above.

---

## Q8 — R:R After Target Revision [application]
> Entry on puts at 392.40, stop at 393.38 (0.98 risk). Original PT1: 391.20 (1.20 pts / 1.22R — already flagged as sub-1.5). Heatseeker shows a cascade fuel setup, retarget to 387.60 (4.80 pts). Does the retargeted R:R clear the gate?

> [!answer]- Answer
> **Yes — retargeted R:R = 4.90R** (4.80 pts / 0.98 risk). The original target at 391.20 failed the 1.5 gate. But after retargeting using Heatseeker cascade data (stacked -GEX below, King shrinking), the 387.60 stretch target gives 4.90R — well above the 1.5 minimum. Rule applied correctly: retarget FIRST, then re-test the gate. (This is Trade 024, TSLA 2026-03-25.)

---

## Q9 — Runner Exit Triggers [recall]
> List 5 triggers that tell you to exit a runner (first one that fires = exit).

> [!answer]- Answer
> Any 5 of: (1) Fuel -GEX node decays ≥50% off its peak; (2) King node re-grows to or above pre-break size; (3) At-spot node flips polarity (floor forming under price); (4) Opposing wall suddenly grows between price and target; (5) Gatekeeper absorbs on 2nd test; (6) Target node collapses (shrinks dramatically as price approaches); (7) Price rejects the gatekeeper; (8) Trend structure breaks; (9) Single candle ≥2-3x range bounces back — trail immediately.

---

## Q10 — Re-Entry After Fuel Reload [recall]
> After exiting a runner on fuel-decay, you see the fuel node reload (goes from -$0.9M back to -$10.3M). Is this a signal to immediately re-enter the original puts position?

> [!answer]- Answer
> **No.** A fresh fuel reload is a SEPARATE entry decision — it requires its own independent confirmation: a new PC/trigger in the trend direction, its own stop level, and its own R:R check. Do NOT assume the original runner should have been held. The exit was correct based on the data at the time. The reload creates a new setup — grade it from scratch and enter only with a fresh confirmed PC.
