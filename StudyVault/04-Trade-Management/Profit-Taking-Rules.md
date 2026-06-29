---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 8
keywords: profit taking, PT1, PT2, runner, node reaction, management
---

# Profit-Taking Rules ★★★

#management #ltp #heatseeker

## Core PT Rules

| Situation | Rule |
|-----------|------|
| First large Heatseeker node hit | **Take profit immediately** — first touch almost always reacts |
| Major node stalls price | Take most/all profit unless continuation confirms |
| Node breaks with volume + acceptance | Hold runner ONLY — not full size |
| **PT1 hit on LTP trend trade** | Take partial. Move stop to BE **only if reaction confirms**. Otherwise trail below/above bounce/rejection candle wick |
| Rejection trade against larger trend | Take profit faster at first opposite node/level |
| Bounce/reversal attempt | PT1 at reclaim level or nearest node; no full reversal until hold + reclaim + acceptance |
| Gatekeeper ahead | Scale out into it — do NOT hold full size into gatekeeper |

> [!warning]
> "Move stop to BE" is CONDITIONAL, not automatic after PT1.
> Condition: "only if reaction confirms." If no reaction yet → trail the wick instead.

---

## Runner Validity Conditions

Runner is valid ONLY when:
1. First node/level **breaks AND accepts** (not just touches)
2. Volume continues in direction
3. No opposing wall builds immediately ahead
4. Cascade confirmation: 3-of-3 conditions still intact (see [[Cascade-Confirmation]])

---

## Runner Exit Triggers (exit when FIRST fires)

| Trigger | Action |
|---------|--------|
| Fuel -GEX node decays **≥50% off its peak** | Exit runner — fuel exhausted |
| King node **rebuilds toward/above its pre-break size** | Exit runner — ceiling reasserting |
| At-spot node flips polarity | Tighten immediately |
| Opposing wall suddenly grows between price and target | Scale out |
| Gatekeeper absorbing on 2nd test | Exit most/all |

---

## Oversized Candle Management

> [!important]
> Any single candle running **≥2-3x the recent candle range** in your favor = immediate trigger to TRAIL.
> Do not leave a static stop (even breakeven) through the full point range of the next normal bounce.

```
Example (Trade 025, 2026-03-26):
  Normal candle range: ~1.1-1.8 pts
  Cascade candle: ~4 pts (3.6x normal)
  → Immediate trigger to trail under that candle's structure
  → A flat BE stop gave back 4+ points for 0R
```

---

## Target Selection: LTP Level vs Heatseeker Node

When LTP structural level and Heatseeker node are at different prices:
- If LTP level gives <0.5R from entry → fails R:R → use Heatseeker node as PT1
- If both within reasonable R:R → use nearer one as PT1, farther as PT2

> [!important]
> When Heatseeker justifies a LOWER target → **recompute R:R against the new target**.
> If it fails 1.5 after retargeting = SKIP. Not "take it smaller."

## Related Notes
- [[Runner-and-Stop-Management]]
- [[Cascade-Confirmation]]
- [[Node-Distance-Framework]]
