---
source_pdf: TSLA_Model_Audit.md
part: all audit entries
keywords: practice, model audit, misses, lessons, corrections
---

# Model Audit Practice (8 questions)

#practice #model-audit

## Related Concepts
- [[Key-Lessons]] · [[Common-Traps]] · [[Integration-Framework]]

---

## Q1 — Entry Domain Miss [recall]
> In the PLTR 2026-06-25 trade, what two errors were made simultaneously?

> [!answer]- Answer
> 1. **Failed to identify the failed reclaim level**: the model required the PC to sit AT Hourly 110, but in a failed reclaim, the level is the CEILING above the PC. PC was at 109.13-109.63 (just below 110). The LTP level was Hourly 110 (the ceiling price couldn't get back above).
> 2. **Heatseeker used to second-guess a clean LTP entry**: Heatseeker node oscillation at the 109 strike was interpreted as "momentum slowing" → entry graded B- incorrectly. Should have been A+ on LTP alone; Heatseeker was only relevant for target selection (107 floor, which was accurate).

---

## Q2 — Flat BE Stop Pattern [recall]
> Trades 018 and 025 both lost large gains for 0R. What was the common root cause and what is the fix?

> [!answer]- Answer
> **Common root cause**: flat breakeven stop left through a normal bounce after large favorable movement, without trailing under the candle structure. In Trade 018: PT1 hit → flat BE → chop bounce → 0R. In Trade 025: oversized cascade candle (~4 pts, 3.6x normal range) → flat BE → next normal bounce tagged stop → 0R. **Fix**: (1) After PT1: move to BE ONLY if reaction confirms (new rule). (2) Any single candle ≥2-3x the recent candle range = immediate trail trigger. Never leave a static stop through the full bounce range of a bounce that follows an oversized favorable candle.

---

## Q3 — King Sign vs Magnitude [recall]
> In Trade ~033 (TSLA 2026-03-27), a -$176M→-$220M negative King node was dismissed as "not a wall." What happened and what is the fix?

> [!answer]- Answer
> The model applied the color rule blindly: "-GEX = fuel/accelerant, won't block." Price tagged the 370 node (almost exactly) and reversed hard, stopping the trade. **Fix**: Magnitude > color. A node that is the session's DOMINANT node by a wide margin acts as a real reaction/reversal zone REGARDLESS of sign. Color modulates how it reacts (sharper/more violent for negative vs. sticky/grindy for positive). A -$220M King-level node is NOT "just fuel" — it is the primary reaction zone of the day.

---

## Q4 — Node Recency vs Size [recall]
> In Trade 032 (TSLA 2026-03-27), a large node was used as confirmation for an entry. What was the miss?

> [!answer]- Answer
> The 370.0 node was the largest seen all session (-$33.7M→-$44.7M). But it had already **peaked and started easing** (-$42.6M by the 11:35 PC) before the entry triggered at ~11:40. The model confused "this node is big" with "this node is still actively growing right now." These are different claims — only the second supports a squeeze/overshoot thesis at entry. **Fix**: before any large-node-based entry, check the last 2-3 readings immediately before entry. "Still growing now" ≠ "peaked earlier."

---

## Q5 — Partial Cascade [recall]
> Trade 010 had a valid PC break short with King CLIMBING the whole time. The trade round-tripped. What rule applies?

> [!answer]- Answer
> **2-of-3 cascade = scalp only.** Conditions met: stacked -GEX below (✓), +GEX growing through break (partial ✓). Condition NOT met: King shrinking (✗ — King was climbing continuously throughout). A climbing King = the day's dominant anchor is getting stronger, not weaker → it will pull price back. This is the Partial Cascade (2-of-3) → scalp only rule. The valid PC warranted entry, but only to PT1, not a stretch hold. The round-trip was caused by holding past PT1 without 3-of-3 confirmation.

---

## Q6 — At-Spot Polarity Flip at Confluence [recall]
> Trade 033 (TSLA 2026-03-27): 360.0 flipped from positive to negative, fuel below at 357.5/355.0. Entry triggered on PC-low break. Price wicked to 359.53 and reclaimed above 360. What was missing?

> [!answer]- Answer
> **Bid/ask 5-second hold confirmation** at a psych/Hourly level confluence. 360.0 was both a round number (psych) AND an Hourly Level — exactly the kind of level that produces stop-run wicks. The at-spot node flip was correct (necessary condition), but at a major confluence it is NOT sufficient alone. Required: flip + PA hold (price stays below 360 for a sustained 5-second bid/ask hold). Without the hold = wick-and-reclaim risk confirmed here.

---

## Q7 — Image Cache Timing [recall]
> What is the image cache overwrite problem and when should screenshots be copied?

> [!answer]- Answer
> Heatseeker/chart screenshots shared in chat are cached at `~/.claude/image-cache/<session-id>/<N>.png`. The PROBLEM: cache filenames (like 241.png) are NOT permanently stable — they can be reused/overwritten by later images in the same conversation. Screenshots deferred to "log it" time may have different content by then. **Fix**: copy relevant screenshots into the trade folder (or a temp holding folder) **immediately when analyzed** — not deferred to the logging trigger. If the trade_id isn't finalized yet, use a temp holding location and move them in later.

---

## Q8 — Hindsight Validation Trap [recall]
> After exiting a runner on the fuel-decay signal, price extended further later in the same session. Does this mean the exit was wrong?

> [!answer]- Answer
> **No.** This is the hindsight bias / bad-learning-behavior trap. A trade working despite a wrong exit is an outcome, not validation. The exit was based on data available at the time (fuel node decayed 94%, King rebuilt to new high = cascade over). That read was accurate. The later extension happened AFTER a fresh fuel reload — that is a **separate, new setup** with its own PC and entry conditions. Using the eventual extension to retroactively invalidate the exit would lead to holding through all future chop "just in case" — that is hope, not a managed position. Grade exits on the evidence at the time, same as entries.
