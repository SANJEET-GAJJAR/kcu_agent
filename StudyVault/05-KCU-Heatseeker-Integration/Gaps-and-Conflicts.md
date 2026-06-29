---
source_pdf: TSLA_Model_Audit.md
part: 2026-06-25 synthesis
keywords: gaps, conflicts, KCU, Heatseeker, integration issues
---

# KCU + Heatseeker — Gaps & Conflicts ★★

#integration #model-audit

> Identified 2026-06-25 after reviewing all live and backtest trades.

---

## Gap 1 — No Hard Entry Domain Boundary

**Problem**: Heatseeker bleeds into LTP entry decisions. Model consulted Heatseeker nodes at entry, causing valid A+ setups to be graded B- and weak setups to be inflated.

**Fix**: Two-stage hard separation — LTP stage (Heatseeker closed), then Heatseeker stage (after entry confirmed).

---

## Gap 2 — Node Direction Not Defined

**Problem**: Growing positive node called "ceiling" regardless of which side price was approaching from.

**Fix**: Growing +node from below = magnet. Growing +node from above = ceiling. Must check approach side before calling a reaction.

---

## Gap 3 — Cascade Confirmation Not Connected to Sizing

**Problem**: KCU grade (A/B/C) and Heatseeker cascade score (0-1-2-3-of-3) determined size independently and inconsistently.

**Fix**: Explicit sizing matrix — A/A+ + 3-of-3 = full; A/A+ + 2-of-3 = half; A/A+ + 0-1 = scalp; B + any = half or less.

---

## Gap 4 — No Protocol for "Heatseeker Says Wrong, Stop Not Hit"

**Problem**: Heatseeker signaled early invalidation (King rebuilding, fuel draining) before the KCU stop was hit. No rule said "exit now vs wait for stop."

**Fix**: At-spot polarity flip in first 1-2 candles = early exit trigger. Fuel-decay ≥50% + King rebuild = runner exit trigger. Both override "hold to stop" default.

---

## Gap 5 — Large Negative Node = Fuel or Wall (Undefined by Context)

**Problem**: Massive -GEX nodes (-$176M at TSLA 370, -$8.7M at NVDA 190) were treated as pure fuel when they were actually primary reaction/reversal zones.

**Fix**: If node is King-level magnitude AND at structural confluence (Hourly + round number), treat as violent reaction zone — expect break through OR sharp reversal. Require PA hold confirmation before assuming it breaks.

---

## Gap 6 — Reversal Entry Sequence Not Defined

**Problem**: Heatseeker two-part signal (fuel peak + King deceleration) fires 1-4 min BEFORE price extreme. LTP requires a PC. No rule specifies the sequence: Heatseeker first → then look for PC.

**Fix**: Heatseeker signal fires = watch for PC to form. Enter on PC break. Do NOT enter on Heatseeker signal alone.

---

## Gap 7 — Target Conflict Resolution (LTP Level vs Heatseeker Node)

**Problem**: When the nearest LTP structural level and the nearest Heatseeker node are at different prices, which is PT1?

**Fix**: If LTP level gives <0.5R from entry → fails the R:R gate → use Heatseeker node as PT1. If both within reasonable R:R → nearer = PT1, farther = PT2. Always recompute R:R against chosen target.

## Related Notes
- [[Integration-Framework]]
- [[Heatseeker-Entry-vs-Target]]
- [[Common-Traps]]
