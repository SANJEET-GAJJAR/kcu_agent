---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 7D-E
keywords: rug pull, reverse rug, slingshot, GEX structure, cascade
---

# Rug Pull & Reverse Rug (Slingshot) ★★

#setup #heatseeker

## Rug Pull (Bearish Cascade)

**Structure:** +GEX ceiling stacked above / -GEX fuel below / little/no floor.

```
Map structure:
  ┌─────────────────────┐
  │  +GEX ceiling       │  ← Reject here
  │  (yellow cap)       │
  └─────────────────────┘
       SPOT PRICE
  ┌─────────────────────┐
  │  -GEX fuel          │  ← Accelerates fall
  │  (purple below)     │
  └─────────────────────┘
  [air pocket]
  ┌─────────────────────┐
  │  Little/no floor    │
  └─────────────────────┘
```

**Bearish trigger:** price rejects the +GEX ceiling and falls through -GEX zone; sellers accelerate.

**A+ requires:**
- Air pocket below
- Fresh downside target (untouched node)
- Node growing DURING break (cascade fuel)
- Trend/tape supports direction

**Do not:** short after target already paid out unless new structure forms.

---

## Reverse Rug / Slingshot (Bullish)

**Structure:** -GEX above / +GEX floor below; price flushes into floor and holds.

```
Map structure:
  ┌─────────────────────┐
  │  -GEX above         │  ← Squeeze fuel once broken
  │  (purple cap)       │
  └─────────────────────┘
       SPOT PRICE
  ┌─────────────────────┐
  │  +GEX floor         │  ← Must hold here
  │  (yellow base)      │
  └─────────────────────┘
```

**Bullish trigger:** price flushes into +GEX floor, holds, reclaims above it, shows acceptance.

**If the bounce cannot reclaim the level = bounce scalp only, NOT a reversal entry.**

**First target:** nearest reclaim level or gatekeeper node above.
**Stretch target:** King node or major upside node.

---

## Positive Gamma Bounce vs Full Reversal

| Condition | Read | Action |
|-----------|------|--------|
| First touch of +gamma after flush | Likely bounce/profit-taking, NOT auto-reversal | Scalp only unless hold + reclaim + acceptance |
| +node holds and grows while price bases | Floor strengthening | Long valid if PC forms and risk tight |
| Price bounces but +node GROWS instead of shrinking | Bearish divergence / fake bounce risk | Take profit fast; avoid full-size long |
| Price breaks below +node and node GROWS | Cascade fuel (not floor!) | Puts may be valid toward next node |

---

## Negative Gamma Continuation

- Purple nodes amplify moves in EITHER direction (not simple walls)
- Below price: -GEX = rug fuel for breakdowns
- Above price: -GEX = squeeze fuel for breakouts
- If price enters -GEX zone with volume and no gatekeeper: **do not fade** — trade with momentum or wait for overshoot reaction

## Related Notes
- [[Node-Taxonomy]]
- [[Node-Direction-Rules]]
- [[Cascade-Confirmation]]
- [[Rejection-Failed-Reclaim]]
