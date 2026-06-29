---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 5
keywords: node distance, PT1, target, TSLA 0DTE, node relevance
---

# Node Distance Framework ★★★

#heatseeker #node #ltp

## Distance Relevance Table

| Distance from entry | Relevance | How to use |
|--------------------|-----------|-----------|
| **0–2 pts** | High — critical | Opposing node here can block PT1 → reduce size or skip. Confirming node = stop/invalidation reference. |
| **2–4 pts** | Medium/High | Valid PT1 / primary target. Watch first-touch reaction. |
| **4–7 pts** | Low / Runner only | PT2 or stretch target only. Do NOT use to validate a 1-point scalp entry. |
| **7+ pts** | Irrelevant for entry | Ignore unless it's a King, macro anchor, or special event node. |

---

## Puts Application (entry at price X)

```
X - 1 to X - 2:    Check for BLOCKING support (positive node)
                    If yes → reduce size or skip
X - 2.5 to X - 4:  PT1 / main target zone
                    Check for first-touch reaction at PT1 node
X - 4 to X - 7:    PT2 / runner only
X - 7+:             Ignore for this entry
```

## Calls Application (entry at price X)

```
X + 1 to X + 2:    Check for BLOCKING resistance (negative node)
                    If yes → reduce size or skip
X + 2.5 to X + 4:  PT1 / main target zone
X + 4 to X + 7:    PT2 / runner only
X + 7+:             Ignore for this entry
```

---

## Growing Node Exception (cascade fuel)

> [!important]
> If the node within 0-2 pts is a growing +GEX node that price is BREAKING THROUGH → this is cascade fuel, not a blocker.
> Do NOT cap PT1 at a breaking +GEX node that is growing. Target the next negative nodes below it.

```
Growing +GEX node in path of puts:
  Normal logic: blocking node → reduce/skip
  Cascade exception: if node is growing THROUGH the break → cascade fuel → target is BELOW the node
```

---

## Target Quality Assessment

Before setting PT1, ask:
1. Is there a positive node between entry and PT1 that could block? (0-2 pts)
2. Is the PT1 node fresh (untested this week)? Or has it already paid out?
3. Is the PT1 node growing (real magnet) or declining (weakening target)?
4. Is there an air pocket between entry and PT1? (Fast move = good for direction)

---

## TSLA 0DTE Context

- Typical clean move: 1-point PT1, runners held when structure supports
- Stop sizing must be tight relative to $1 PT1 target to clear R:R ≥1.5
- For NVDA: levels spaced $1.70–2.50 → each leg ≈ $2 → stop must be <$1 to achieve 2R PT1

## Related Notes
- [[Node-Taxonomy]]
- [[Node-Direction-Rules]]
- [[Profit-Taking-Rules]]
- [[Cascade-Confirmation]]
