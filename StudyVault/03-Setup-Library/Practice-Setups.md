---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf, kcu_framework.md
part: section 7
keywords: practice, setups, LTP, rejection, rug pull, no trade
---

# Setup Library Practice (10 questions)

#practice #setup

## Related Concepts
- [[LTP-Trend-Pullback]] · [[Rejection-Failed-Reclaim]] · [[Rug-Pull-Reverse-Rug]] · [[No-Trade-Conditions]]

---

## Q1 — Failed Reclaim Entry [application]
> TSLA breaks below VWAP at 391. Price bounces to 390.70 but fails to close above VWAP (391). A contained green candle forms at 390.40–390.70. What is the setup, what is the level, where is the entry and stop?

> [!answer]- Answer
> **Setup: Failed Reclaim Short.** Level = VWAP at 391 (the ceiling price could NOT get back above). PC = contained green candle at 390.40-390.70. Entry = break below PC low (~390.40). Stop = above PC high (~390.75). This is an A-quality LTP setup if trend is down and R:R clears 1.5.

---

## Q2 — Rug Pull vs Reverse Rug [recall]
> Describe the Heatseeker map structure for a Rug Pull and a Reverse Rug. What is the key structural difference?

> [!answer]- Answer
> **Rug Pull (bearish)**: +GEX ceiling above + -GEX fuel below + little/no floor. Price rejects the ceiling and falls through fuel. **Reverse Rug (bullish)**: -GEX above + +GEX floor below. Price flushes into the floor and holds. Key difference: the relative position of positive and negative gamma. In a rug pull, the positive is above (resistance) and negative is below (fuel for the fall). In a reverse rug, the positive is below (support) and negative is above (squeeze fuel when broken).

---

## Q3 — Setup Comparison [analysis]
> You see: clean 5m downtrend, TSLA at VWAP, OR Low just below (clean level), PC forming at VWAP from below. What is the BEST setup available, and what would make this a no-trade?

> [!answer]- Answer
> **Best setup: Advanced VWAP / VWAP Rejection Short** (price rejecting VWAP from below after testing it) OR **Failed Reclaim Short** (if price already broke below VWAP and is retesting). With OR Low just below: check R:R from entry to OR Low. If OR Low is 1+ pt below with stop 0.5-0.6 above VWAP = ~1.7-2R → valid. **No trade if**: R:R fails 1.5 (OR Low too close to entry), PC is large/ambiguous, trend is choppy, or same test already failed today.

---

## Q4 — Reversal vs Rejection [recall]
> What is the key difference between a Rejection and a Reversal? Why can't one rejection candle be called a reversal?

> [!answer]- Answer
> **Rejection** = price approaches a level, touches/gets near it, and sharply moves away — one event, one reaction. Can happen in any trend context. **Reversal** = prior trend + weakness + structure break + PC. Takes time to form — needs structural breakdown of the prior trend, not just one sharp candle. One rejection candle = REJECTION_WATCH. Only after prior trend + structure break + PC = REVERSAL_WATCH. The KCU framework says: "Do not call reversal from one rejection candle."

---

## Q5 — No Trade Identification [application]
> TSLA is at 395, between VWAP (394.50) and OR High (396.50). Trend is mixed, 2m shows one HH but then an LL. A PC has formed but VWAP is 0.5 pts below and OR High is 1.5 pts above. What is the correct call?

> [!answer]- Answer
> **No trade / CHOP_STAY_OUT.** Multiple reasons: (1) Trend is mixed (one HH then LL = no clean structure); (2) Price is between VWAP and OR High = in the middle of the range; (3) No clean level — PC is floating between two levels; (4) VWAP 0.5 pts below would block PT1 on a long trade (0-2 pt zone). The correct call is to wait for: price to clearly break and accept above OR High (then look for a pullback PC), or below VWAP (then look for a rejection/failed reclaim from below).

---

## Q6 — Sloppy Seconds [application]
> TSLA has already tested and reacted cleanly from the 390 node once today (Trade 002, won 1.82R). Now an hour later, price is back at 390 with a new PC. Should you take the trade?

> [!answer]- Answer
> **Downgrade to B-/C+ at most; scalp only.** 390 has already paid out this session — this is "sloppy seconds." The first touch gets the best reaction. The second test may still work but expect a diminished/choppier reaction. Exception: if the 390 node has GROWN significantly since the first test (rebuilding as a stronger floor/ceiling), it may still be tradeable at B. Do not expect a clean repeat of the first reaction's character. Size down and take profit faster.

---

## Q7 — OR Bounce/Reject [recall]
> What is the KCU ORB Bounce/Reject setup and what does it require?

> [!answer]- Answer
> **ORB Bounce/Reject**: price breaks out of the 15-minute Opening Range. Then retests the ORB level (OR High or OR Low). Setup requirements: (1) Price tests the ORB level from the breakout side; (2) A PC forms at the ORB level; (3) Entry uses standard PC logic (break of PC); (4) Stop is PC-based; (5) Target = nearest intraday/hourly level. Skip if no PC or no confluence. This is classified as PARTIALLY_COVERED — stop/target not fully defined in extracted rules.

---

## Q8 — Gatekeeper Reaction [application]
> Price is approaching the Gatekeeper node at 400 for the THIRD time today. Each prior test held. You are watching for a short entry. What is the correct setup?

> [!answer]- Answer
> On the **third test**, the probability shifts toward the gatekeeper BREAKING — do not fade the third test. Instead: (1) Do NOT take the standard rejection short at 400 on this third approach; (2) Watch for a gatekeeper break (acceptance above 400) — if it breaks and accepts, look for calls (squeeze fuel above); (3) If it rejects again (unexpected), the signal would be very significant but require a clean PC and be sized carefully. The third test is NOT a guaranteed fade and NOT a guaranteed break — it's a watch-and-react moment.

---

## Q9 — Advanced VWAP Contradiction [recall]
> What is the known contradiction in the Advanced VWAP setup from KCU training? How should it be applied?

> [!answer]- Answer
> **Contradiction**: Some extracted KCU training notes say Advanced VWAP needs trend/trendy stock. Some say it works in chop. Some say it does NOT work in strong trend. **Working interpretation**: (1) Do not use in random chop; (2) Do not use in runaway trend far extended from VWAP; (3) Best in controlled pullback/reclaim of VWAP after price came from below, with PC and room to target; (4) Size conservatively and note: "market context is contradictory in training notes." Status: PARTIALLY_COVERED / CONTRADICTORY.

---

## Q10 — Time of Day Discipline [recall]
> At 11:45 AM, a setup appears that grades A- on LTP with R:R of 2.1. Should it be taken?

> [!answer]- Answer
> **Lower confidence — scalp only or skip.** 11:45 AM falls in the lunch dead zone (11:20–1:00 PM): thin liquidity, choppy moves, setups that trigger often fail to follow through due to low volume. Per session discipline rules: "Avoid or scalp only with exceptional structure" during lunch. An A- at 11:45 would be graded down — take it as scalp only (half size, PT1 target, no runner) or skip and wait for the 1:00 PM afternoon reset. If the setup is truly exceptional (fresh level, perfect PC, strong trend continuation), note the time downgrade and size very conservatively.
