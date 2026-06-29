---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf, TSLA_Model_Audit.md
part: sections 4, 5, 6
keywords: practice, Heatseeker, nodes, King, cascade, magnitude
---

# Heatseeker Practice (10 questions)

#practice #heatseeker

## Related Concepts
- [[Node-Taxonomy]] · [[Node-Direction-Rules]] · [[Node-Distance-Framework]] · [[Heatseeker-Entry-vs-Target]]

> [!hint]- Key Patterns
> | Keyword | Answer |
> |---------|--------|
> | Magnitude rule | -80M > +20M regardless of color |
> | Growing +node from below | Magnet/target — NOT a ceiling |
> | Growing +node from above | Ceiling/resistance |
> | Node draining as approached | Will pass through (being consumed) |
> | Flip negative at session extreme | Exhaustion → flip back = bounce confirmed |
> | 3-of-3 cascade | +GEX grows through break + stacked -GEX below + King shrinking |

---

## Q1 — Node Types [recall]
> Name all 7 node types and their colors/meanings.

> [!answer]- Answer
> 1. **+GEX / Yellow / Pika**: stabilizer, magnet/target, sticky S/R — use as floor/ceiling or PT
> 2. **-GEX / Purple / Barney**: accelerator, fuel, amplifies moves — trade with momentum
> 3. **King**: highest absolute exposure, daily anchor, gravity center — primary reaction zone regardless of sign
> 4. **Gatekeeper**: ≥1/4 King size, between spot and King, obstacle — fade 1st/2nd test
> 5. **Air Pocket**: sparse/zero nodes — fast movement zone, don't fade
> 6. **Hedge Node**: large, news/event related — ignore normally, respect at events
> 7. **Dark Pool Level**: hidden institutional liquidity via Atlas — mark as reaction/target if respected

---

## Q2 — Magnitude Rule [application]
> Two nodes: +GEX at +$3.2M and -GEX at -$8.7M. Which takes priority? Why?

> [!answer]- Answer
> The **-$8.7M negative node** takes priority. Magnitude > color always. A -$8.7M node is ~2.7x larger in absolute terms than the +$3.2M node. The color (-GEX) explains HOW it reacts (more violently, as an accelerator), but the SIZE determines WHETHER it's an important level. Never dismiss a King-level negative node just because it's purple.

---

## Q3 — Node Direction [application]
> NVDA bounces from a session low at 192.13 toward 195. The 195 node TRIPLES from +$935K to +$2,744K while price is at 194.52 moving up. Is this a ceiling or a magnet? What happens?

> [!answer]- Answer
> This is a **MAGNET/TARGET** — not a ceiling. Price is approaching 195 from BELOW. A growing positive node with price below it pulls price TOWARD it, not away from it. Price will likely move through 195 toward the next resistance (OR Low, structural level). The actual ceiling/rejection came at the OR Low (~195.90), not the 195 node. The 195 node was also draining (2,744K → 1,854K → 1,822K) as price approached = being consumed = no rejection there.

---

## Q4 — Cascade 3-of-3 [recall]
> What are the three conditions required for a full cascade confirmation (stretch hold)?

> [!answer]- Answer
> 1. **+GEX node grows THROUGH the break** (the node price broke below is getting larger, not smaller = cascade fuel, not a floor)
> 2. **Stacked negative nodes beneath** price and growing
> 3. **King shrinking** (the dominant ceiling node is softening = less resistance to continued downside)
> All three required for a stretch runner. 2-of-3 = scalp to PT1 only. 1-of-3 = very tight scalp.

---

## Q5 — Node at Session Extreme [application]
> During a cascade, TSLA's 192.5 node reads: 9:45 = +$2,136K → 9:50 = +$894K → 9:57 = -$146K → 10:03 = +$330K → 10:10 = +$606K. What do you conclude at each stage?

> [!answer]- Answer
> - 9:45 → 9:50: Floor shrinking but still present. Watch closely — put momentum valid toward 192.5.
> - 9:57: **Flip to negative** = floor temporarily exhausted. Cascade fuel active here. Low of cascade likely nearby.
> - 10:03: **Flipped back positive** = floor re-establishing. Bounce is real and confirmed.
> - 10:10: Growing positive = floor strengthening. Do not hold puts expecting continuation past 192.5 without new fuel.
> Key rule: negative flip at session extreme = exhaustion, not permanent regime change.

---

## Q6 — King Distance Decay [application]
> King node is at 400 and worth $25M when price is at 400. Price moves to 394 and King drops to $18M. Is this a reversal signal? Explain.

> [!answer]- Answer
> **No — this is distance decay**, not a reversal signal. As price moves AWAY from the King node (from 400 to 394, 6 pts away), the node's GEX value mechanically declines because the delta hedging requirement decreases with distance. This is expected and normal. A reversal signal would be King decelerating/collapsing while price is STILL AT or NEAR the King level, not while price is moving away from it.

---

## Q7 — Heatseeker Entry Rule [recall]
> When should Heatseeker be consulted for LTP continuation trade entries? When should it be consulted for rejection/reversal entries?

> [!answer]- Answer
> **LTP continuation**: Heatseeker should NOT be consulted for the entry go/no-go decision. Close Heatseeker during the LTP entry check. Open it ONLY after LTP says go — to set PT1 target, determine sizing (cascade score), and monitor for runner validity. Using Heatseeker to second-guess a clean LTP entry inverts the priority stack.
> **Rejection/reversal**: Heatseeker IS the primary tool — the local node reaction IS the trade thesis. The node is both the level and the entry reason. PC still required for trigger timing.

---

## Q8 — Gatekeeper Rules [recall]
> What is a gatekeeper? What are the rules for trading at a gatekeeper?

> [!answer]- Answer
> Gatekeeper = a significant node between spot and King, typically ≥1/4 to 1/3 of King's size. Rules: (1) Fade the 1st test — first approach tends to hold; (2) Fade the 2nd test — may also hold; (3) 3rd test: probability shifts toward break — don't fade, watch for absorption; (4) When gatekeeper's value fades or is repeatedly tested with price holding near it, watch for break. Always scale out as price approaches a gatekeeper even if holding a runner.

---

## Q9 — Node Distance [application]
> Entry on puts at 395.00, stop at 395.90 (0.90 pt risk). Nodes: +$1.2M at 394.50 (+0.5 pts below). +$3.5M at 393.00 (2.0 pts below). -$4.0M at 390.00 (5 pts below). What's the correct action?

> [!answer]- Answer
> - 394.50 (+$1.2M, 0.5 pts below): within 0-2 pt zone = **potential PT1 blocker** — evaluate if this node can stop the first 0.5 pt move. Small positive here = may not block but will slow. Flag.
> - 393.00 (+$3.5M, 2.0 pts below): in 2-4 pt zone = **valid PT1** (entry 395, stop 395.90 → risk 0.90 → PT1 at 393 = 2.0 pts = 2.22R ✓)
> - 390.00 (-$4.0M, 5 pts below): 4-7 pt zone = PT2/runner only, don't validate the entry on this node alone
> Correct action: set PT1 at 393 (~2.22R), be aware of 394.50 speed bump, hold runner to 390 only if cascade confirms.

---

## Q10 — Air Pocket [recall]
> When you see an air pocket between current price and the target node, what does this mean for your entry and exit strategy?

> [!answer]- Answer
> Air pocket (sparse/zero nodes between current price and target) means: (1) **Fast movement zone** — price can move quickly without meaningful S/R slowing it down; (2) **Great for the path** — the air pocket supports your directional target with less friction; (3) **Do NOT use as a blind entry zone** — no nodes to anchor a counter-trade or give you a level; (4) **Exit strategy in air pockets**: Heatseeker gives the structure, PA (patience candle behavior, timeframe switch signals) gives the exit timing. A "Use 5m" signal at the air pocket bottom is the PA signal to watch.
