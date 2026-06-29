---
source_pdf: TSLA_Model_Audit.md, TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: integration section
keywords: practice, integration, KCU Heatseeker, conflict, priority
---

# KCU + Heatseeker Integration Practice (8 questions)

#practice #integration

## Related Concepts
- [[Integration-Framework]] · [[Heatseeker-Entry-vs-Target]] · [[Common-Traps]]

---

## Q1 — Entry Domain [recall]
> At what stage should Heatseeker first be consulted for an LTP trend continuation trade?

> [!answer]- Answer
> **After the LTP entry is confirmed** — not during. The sequence: (1) Check LTP: Level + Trend + PC + R:R → if go, proceed; (2) THEN open Heatseeker to find PT1 (next positive floor for puts, or negative fuel zone for calls), set sizing (cascade score), identify runner target, and monitor for exit signals. Using Heatseeker to second-guess a confirmed LTP entry inverts the priority stack and causes grade distortion.

---

## Q2 — Conflict: Strong Heatseeker, Weak LTP [application]
> Heatseeker shows King shrinking + stacked -GEX below (strong cascade confirmation). LTP: PC exists but is large (wide range), and trend is choppy on both 2m and 5m. What's the correct action?

> [!answer]- Answer
> **Skip or scalp only.** LTP = go/no-go. Strong Heatseeker does NOT upgrade a weak LTP entry. With a large PC and choppy trend, the LTP is at best a C-grade. Heatseeker confirmation moves the sizing, not the entry decision: weak LTP = scalp only at best, regardless of how strong the node setup is. The correct thing to say is: "Heatseeker confirms direction but LTP is C — entry quality insufficient, no trade or tiny scalp."

---

## Q3 — Conflict: Strong LTP, Warning Heatseeker [application]
> Clean A+ LTP short: clear trend, tight PC at OR Low, excellent R:R. Heatseeker: 195 positive node is +$1.8M and GROWING below entry. This could block PT1. What's the correct action?

> [!answer]- Answer
> **Go on the LTP, but adjust sizing and PT1.** Trust LTP for entry. Use Heatseeker warning to: (1) flag the +$1.8M node as a potential speed bump — place PT1 at or before it; (2) reduce to half size (node blocking PT1 within 0-2 pts = reduce or skip per node distance rules); (3) don't use a stretch target past the blocking node without seeing it drain first. Do NOT skip the A+ LTP entry just because Heatseeker shows a node.

---

## Q4 — Rejection: Heatseeker as Entry [application]
> PLTR opens at 113.51 with a massive King node at 114 (-$3.1M). Stacked negative nodes below (113/112/111 all negative). No LTP structure at the open. Is this a valid entry thesis? On what basis?

> [!answer]- Answer
> Yes — this is a **King Node Rejection** setup where Heatseeker IS the entry reason. The King at 114 is both the structural level AND the entry basis. Price opening directly under the King (-$3.1M ceiling) with stacked negative fuel below = short thesis. PC still required for entry timing (wait for a PC to form after the first rejection candle). This is one of the two setups where Heatseeker is primary at entry (King fade and Gatekeeper fade).

---

## Q5 — Target Conflict [application]
> Entry on puts at 395.00, stop at 395.60 (0.60 pt risk). Nearest LTP structural level below = 394.50 (0.5 pts = 0.83R). Nearest Heatseeker positive floor = 393.00 (2.0 pts = 3.33R). Which is PT1?

> [!answer]- Answer
> **Heatseeker node at 393.00 is PT1.** LTP structural level at 394.50 gives only 0.83R — below the 1.5 gate. The Heatseeker node at 393.00 gives 3.33R — well above the gate. Per the target conflict rule: when the LTP level gives <0.5R (actually ~0.83R here, so borderline) and the Heatseeker node gives ≥2R, use the Heatseeker node as PT1. Always verify by recomputing R:R against whichever target you choose.

---

## Q6 — Reversal Sequencing [application]
> At the cascade bottom, the Heatseeker two-part reversal signal fires (fuel node peaks + King decelerates). Price has not yet printed a PC. What is the correct action for a long entry?

> [!answer]- Answer
> **Wait for the PC — don't enter on Heatseeker signal alone.** The two-part signal is a LEADING signal with a 1-4 minute lead time before the actual price extreme. Use it to: (1) Start tightening/covering any existing short; (2) Anticipate a bounce-scalp long entry; (3) Watch for a PC to form as price finds its extreme. Entry: break above PC high (LTP trigger) after the Heatseeker signal has fired. The Heatseeker signal tells you WHEN to look for the PC, not to enter without it.

---

## Q7 — Heatseeker for Air Pocket Exit [application]
> Price is in an air pocket between 192.5 (old positive node that flipped negative) and 190.00 (massive -GEX negative node). The 192.13 low forms and "Use 5m" indicator signal appears. Heatseeker still shows 190 as the target (-$8.7M). Should you hold puts expecting 190?

> [!answer]- Answer
> **No — exit or tighten significantly.** In an air pocket, Heatseeker gives the structure (190 is the target) but PA gives the exit timing. The "Use 5m" signal = indicator flagging that 2m chart is too noisy and a timeframe switch is needed — this is an exhaustion signal at the bottom. The 190 node being large is a directional magnet but NOT a guarantee of arrival after a large cascade. Seller exhaustion can reverse price before reaching the magnet. Take profits at/near the air pocket bottom, not holding to 190.

---

## Q8 — Gap Analysis [analysis]
> What is the most important structural gap between KCU and Heatseeker, and how does it manifest in real trades?

> [!answer]- Answer
> **The entry domain boundary.** KCU (LTP) is a binary go/no-go snapshot. Heatseeker is a continuous, dynamic gamma read. The gap: no hard rule prevents Heatseeker from being consulted during LTP entry decisions, causing: (1) valid A+ entries downgraded when nodes oscillate; (2) weak entries upgraded when nodes look bullish; (3) incorrect grades on multiple trades. Manifestation: PLTR 2026-06-25 — A+ LTP entry graded B- because model consulted Heatseeker at entry and interpreted node shrinkage as "momentum slowing." Fix: hard two-stage process — LTP first (closed to Heatseeker), Heatseeker second (closed to LTP entry decision).
