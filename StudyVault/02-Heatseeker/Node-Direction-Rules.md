---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 4, NVDA/PLTR educational trades 2026-06-25
keywords: node direction, magnet, ceiling, floor, approach side, polarity flip
---

# Node Direction Rules ★★★

#heatseeker #node

> [!important]
> **Same node, opposite implication depending on which side price is approaching from.**
> This is the most commonly misread Heatseeker concept.

---

## The Direction Rule

| Price approaching from | +GEX node growing | Interpretation |
|------------------------|-------------------|----------------|
| **ABOVE** | ✓ growing | **Ceiling / sticky resistance** — will slow price |
| **BELOW** | ✓ growing | **Magnet / target** — pulls price TOWARD it, not a rejection point |

```
Example (NVDA 2026-06-25, 10:06 AM):
  195 node tripled (+$935K → +$2,744K)
  Price was at 194.52, approaching 195 FROM BELOW
  → This was a MAGNET pulling price toward 195, not a ceiling
  → Price passed through 195 to OR Low (195.90)
  → Actual rejection was at OR Low (PA level), not the 195 node
```

---

## Node Draining = Being Consumed

When a node DRAINS as price approaches it (from either side):
- The node is being consumed/absorbed as price passes through
- Price will likely move through, not bounce at the node
- A node holding its magnitude as price approaches = more likely to cause reaction

```
195 node 10:06 → 10:10:
  2,744K → 1,854K → 1,822K (declining as price rose through it)
  → Confirmed: node consumed, not a wall
```

---

## Polarity Flip Patterns

### At Session Extreme (Low or High)
- Positive node flips NEGATIVE at session low = **temporary exhaustion of floor energy**
- When it flips BACK to positive shortly after = **bounce/floor confirmed**
- This is NOT a permanent regime change

```
NVDA 192.5 node example:
  9:45 AM: +$2,136K (healthy positive floor)
  9:50 AM: +$894K (shrinking)
  9:57 AM: -$146K (FLIPPED negative — at session low!)
  10:03 AM: +$330K (rebuilt positive)
  → Negative flip at session low = exhaustion
  → Positive rebuild = bounce validated ✓
```

### At Psych/Hourly Level Confluence
- Node flips negative at a round-number + Hourly Level = **NOT necessarily a confirmed break**
- These confluences produce stop-run wicks
- Required: node flip + **bid/ask 5-second hold** beyond the level

> [!warning]
> At major psych/Hourly confluences: flip is necessary but NOT sufficient. Need PA hold confirmation.

---

## Massive Negative Node = Target, Not Guaranteed Arrival

- A large -GEX node far below price = directional magnet/target
- After a large cascade, seller exhaustion can reverse price BEFORE the node is reached
- The node tells you WHERE price is headed, not THAT it will get there this session

```
NVDA 190 node (-$8,702K) example:
  190 was growing throughout the cascade
  Price reversed at 192.13 (2.13 pts above 190)
  → 190 node was the directional target — but exhaustion stopped price short
  → Do NOT hold positions expecting the node to always be reached
```

---

## Summary Decision Tree

```
Before calling a node a ceiling or floor, answer:
│
├── Which side is price approaching from?
│   ├── From above + growing → CEILING
│   └── From below + growing → MAGNET (not ceiling)
│
├── Is the node growing or draining as price approaches?
│   ├── Growing → will react (slow/bounce)
│   └── Draining → will pass through (being consumed)
│
└── Is this a session extreme (low/high)?
    ├── Node flipped negative at extreme → exhaustion
    └── Node rebuilds positive → bounce confirmed
```

## Related Notes
- [[Node-Taxonomy]]
- [[Node-Distance-Framework]]
- [[Heatseeker-Entry-vs-Target]]
- [[Common-Traps]]
