---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 4
keywords: node types, King, Gatekeeper, Air Pocket, GEX, magnitude rule
---

# Node Taxonomy ★★★

#heatseeker #node

## Node Types

| Node | Color | Meaning | Action |
|------|-------|---------|--------|
| **+GEX / Yellow / Pika** | Yellow | Stabilizer, sticky S/R, magnet/target | Use as floor/ceiling or PT. If price breaks below and it GROWS → cascade fuel |
| **-GEX / Purple / Barney** | Purple | Accelerator, amplifies moves, fuel | Trade with momentum; expect overshoot and violent reaction |
| **King Node** | Largest absolute | Highest absolute exposure, daily gravity center/anchor | Primary reaction zone regardless of sign — magnitude overrides color |
| **Gatekeeper** | Large, ≥1/4 King | Between spot and King; obstacle/bouncer | Fade 1st/2nd test. 3rd test favors break. Scale out as price approaches |
| **Air Pocket** | Near-zero | Sparse/no nodes between levels | Fast movement zone — great for target path, NOT a blind entry zone |
| **Hedge Node** | Large protective | News/event-related positions | Ignore normally; respect on CPI/FOMC/earnings or if price approaches |
| **Dark Pool Level** | Atlas | Hidden institutional liquidity | Mark as reaction/target/invalidation if price respects it |

---

## ⚑ Magnitude Rule (most important)

> **Magnitude > color. Always.**
> A -80M node matters more than a +20M node regardless of sign.
> Color explains HOW it reacts; absolute size explains WHETHER it's important.

```
Example:
  +GEX node: +$20M → minor magnet
  -GEX node: -$80M → major reaction zone
  → The -$80M node takes priority even though it's negative
```

> [!warning]
> Never dismiss a dominant King-magnitude node just because it's negative (-GEX).
> A massive -GEX King is still a real reaction/reversal point. It reacts MORE violently, not less.

---

## King Node Rules

1. King = highest ABSOLUTE exposure (magnitude), regardless of sign
2. King = daily gravity center — price tends to oscillate around it
3. Shrinking King = ceiling softening (supports a downside move)
4. Growing King + price above it = ceiling hardening (resistant to upside)
5. Distance decay: King declines as price MOVES AWAY from it — this is NOT a reversal signal

```
King distance decay (NOT reversal):
  King at 400, price moves to 395 → King magnitude declines
  This is because the 400 node is now 5 pts away from spot
  → Decline is mechanical distance effect, not a bearish signal
  
King deceleration (IS reversal warning):
  King at 400, price is AT 400 or approaching → King stops growing and rolls over
  → This CAN indicate exhaustion at the level
```

---

## Gatekeeper Rules

- Gatekeeper = significant node between spot and King (≥1/4 to 1/3 of King size)
- **Fade 1st test** — first approach tends to hold
- **Fade 2nd test** — second approach may also hold
- **3rd test: watch for break** — probability shifts toward the gatekeeper being absorbed
- When gatekeeper value fades through repeated tests = break incoming

---

## Air Pocket Rules

- Air pocket = sparse or zero nodes between two levels
- Fast movement zone — price can move several points without meaningful S/R
- **Do not fade in an air pocket** — no nodes to anchor a counter-trade
- Air pockets are great for target paths; terrible for blind entries
- Entry from a node/level INTO an air pocket is the ideal setup structure

---

## Node State — Growing vs Draining

| Node state | Interpretation |
|------------|---------------|
| Growing through a break | Cascade fuel (even if positive node!) |
| Growing while price bases | Floor/ceiling strengthening |
| Draining as price approaches | Being consumed — price will pass through |
| Draining after cascading | Cascade is losing fuel — exit runner |
| Flip negative at session extreme | Exhaustion signal — bounce likely |
| Flip back positive after session extreme | Bounce/floor confirmed |

## Related Notes
- [[Dealer-Model-Regimes]]
- [[Node-Direction-Rules]]
- [[Node-Distance-Framework]]
- [[Cascade-Confirmation]]
