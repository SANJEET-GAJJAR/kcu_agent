---
source_pdf: TSLA_Model_Audit.md
part: all entries 2026-06-19 to 2026-06-25
keywords: model audit, lessons, misses, corrections, root cause
---

# Model Audit — Key Lessons ★★★

#model-audit

> These are documented model misses. The purpose is to not repeat them.

---

## Entry Lessons

### L1 — Heatseeker must NOT gate LTP entries (2026-06-25)
- **Miss**: Used Heatseeker node oscillation to downgrade an A+ LTP entry to B-
- **Fix**: When LTP is A/A+, don't consult Heatseeker for the entry decision
- Trade: PLTR_20260625 → [[Rejection-Failed-Reclaim]]

### L2 — Failed reclaim level = ceiling above PC, not where PC sits (2026-06-25)
- **Miss**: Required PC to be AT the level → called "no clean level" when PC was just below Hourly 110
- **Fix**: In failed reclaim setups, the level is the ceiling price could NOT get back above
- Trade: PLTR_20260625 → [[LTP-Levels]]

### L3 — Velocity ≠ momentum chase (Trade 001, 2026-06-18)
- **Miss**: Dismissed a valid contained-PC as "momentum chase" because prior cascade was vertical
- **Fix**: Vertical cascade = velocity context (caps size), but a clean contained PC at a level is still a valid LTP entry
- Trade: 001 → [[LTP-Trend-Pullback]]

### L4 — Node size ≠ node still actively growing (Trade 032, 2026-03-27)
- **Miss**: Large node (-$44.7M) treated as confirmation without checking it had already peaked 3 min before entry
- **Fix**: Check last 2-3 readings immediately before entry — not absolute size, but current momentum
- Trade: 032 → [[Node-Taxonomy]]

### L5 — Massive negative King must not be dismissed as "just fuel" (Trade ~033, 2026-03-27)
- **Miss**: -$176M→-$220M negative node dismissed as "accelerant, won't block" → price tagged it and reversed
- **Fix**: Magnitude > color. King-level negative node = real reaction zone regardless of sign
- Trade: ~033 → [[Node-Taxonomy]]

---

## Node Reading Lessons

### L6 — Growing positive node from below = magnet, not ceiling (NVDA 2026-06-25)
- **Miss**: 195 node tripling at 10:06 called as ceiling → price moved through 195 to OR Low
- **Fix**: Same node, opposite implication depending on which side price approaches from
- Trade: NVDA_20260625 → [[Node-Direction-Rules]]

### L7 — Node draining as price approaches = will pass through (NVDA 2026-06-25)
- **Miss**: Assumed a node holding magnitude = a wall even while it was actively draining
- **Fix**: Node draining as price approaches = being consumed, price will pass through
- Trade: NVDA_20260625 → [[Node-Direction-Rules]]

### L8 — Negative flip at session low = exhaustion, not regime change (NVDA 2026-06-25)
- **Miss**: 192.5 flip to negative at the cascade low read as continued bearish pressure
- **Fix**: Node flip negative at session extreme = temporary exhaustion. Flip back to positive = bounce confirmed
- Trade: NVDA_20260625 → [[Node-Direction-Rules]]

### L9 — Partial cascade (2-of-3) → scalp only (Trade 010, 2026-06-17)
- **Miss**: Valid LTP entry taken as a stretch hold when King was CLIMBING (2-of-3 only). Round-tripped.
- **Fix**: 3-of-3 required for runners. 2-of-3 = scalp to PT1 only.
- Trade: 010 → [[Cascade-Confirmation]]

### L10 — Re-check King at every leg, not once (Trade 012, 2026-06-17)
- **Miss**: King was flat for 16 min, capped target at King level. King then SURGED through break as fuel.
- **Fix**: When King is also the breaking node, flat ≠ "it will hold." Re-check at each leg.
- Trade: 012 → [[Cascade-Confirmation]]

---

## Management Lessons

### L11 — Flat BE stop after oversized candle gives back winners (Trades 018/025)
- **Miss**: PT1 hit → flat BE stop → oversized bounce → 0R outcome twice
- **Fix**: Any candle ≥2-3x recent range = immediate trail trigger under that candle's structure
- Trades: 018, 025 → [[Runner-and-Stop-Management]]

### L12 — "Move to BE" is conditional, not automatic (Trade 018)
- **Miss**: Cited "matches the playbook" without checking if "reaction confirms" condition was met
- **Fix**: Explicitly check: has a reaction candle confirmed in the trend direction? If yes → BE. If no → trail wick.
- Trade: 018 → [[Runner-and-Stop-Management]]

### L13 — Retarget first, THEN re-test R:R gate (Trade 030)
- **Miss**: Heatseeker justified a lower target. R:R was never recomputed against the new target. Entry taken at sub-1.5 R:R.
- **Fix**: When target is revised downward → recompute R:R → if fails 1.5 = SKIP, not "take it smaller"
- Trade: 030 → [[Profit-Taking-Rules]]

### L14 — Heatseeker replay scrubber ≠ live data (2026-06-22)
- **Miss**: Corner timestamp on Heatseeker screenshot misread as "live now" when it was historical replay scrubber data
- **Fix**: Before declaring historical data unavailable, check for replay scrubber UI at bottom of Skylit screenshot
- Session: LIVE_003 → [[Heatseeker-Entry-vs-Target]]

---

## Process Lessons

### L15 — Copy screenshots immediately, not deferred to log trigger (Trade 016)
- **Miss**: Screenshots assumed to be safe in image cache until "log it" → cache files overwritten by later images
- **Fix**: Copy screenshots to trade folder (or temp holding) as soon as they're discussed in conversation
- Trade: 016

## Related Notes
- [[Common-Traps]]
- [[Integration-Framework]]
- [[Node-Direction-Rules]]
