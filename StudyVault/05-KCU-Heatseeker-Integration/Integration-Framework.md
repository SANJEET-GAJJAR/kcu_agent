---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf, TSLA_Model_Audit.md 2026-06-25
keywords: integration, KCU Heatseeker, priority, entry domain, conflict resolution
---

# KCU + Heatseeker Integration Framework ★★★

#integration #ltp #heatseeker

## The Core Separation

| Domain | Tool | Timing |
|--------|------|--------|
| **Entry go/no-go** | **KCU LTP only** | At setup formation |
| **Target selection** | Heatseeker (nodes) + LTP (structural levels) | After entry confirmed |
| **Sizing** | Heatseeker (cascade score) + KCU grade | After entry confirmed |
| **Runner management** | Heatseeker (fuel/King monitoring) | Continuously post-entry |
| **Early exit** | Heatseeker (at-spot flip) + PA | First 1-2 candles post-entry |

---

## Two-Stage Decision Flow

```
STAGE 1 — Entry (LTP only, Heatseeker CLOSED):
  L: Real level present? ✓
  T: Trend confirmed? ✓
  P: PC clean and contained? ✓
  R:R: ≥ 1.5? ✓
  → ENTRY CONFIRMED
  
STAGE 2 — After entry (Heatseeker OPENS):
  PT1: What is the next positive floor (puts) or negative fuel zone (calls)?
  Size: Cascade 3-of-3 confirmed? → fuller size. Partial → scalp.
  Runner: King shrinking? Fuel growing through break? → hold.
  Exit: Fuel decaying 50%+? King rebuilding? → exit runner.
```

---

## Sizing Matrix

| KCU Grade | Heatseeker Cascade Score | Final Size |
|-----------|--------------------------|------------|
| A+ / A | 3-of-3 | Full |
| A+ / A | 2-of-3 | Half |
| A+ / A | 1-of-3 or 0 | Scalp only |
| B+ / B | 3-of-3 | Half |
| B+ / B | 2-of-3 | Small / scalp |
| C | Any | Scalp only |
| Any | No cascade signal | Size per KCU grade only |

---

## When They Conflict

### Heatseeker says strong, LTP says weak
- Trust LTP for entry go/no-go
- If LTP says B- or C but Heatseeker says strong → take scalp only or skip
- Never let Heatseeker upgrade a bad LTP entry

### LTP says strong, Heatseeker says warning
- Trust LTP for entry — go
- Use Heatseeker warning for: smaller size, tighter stop, faster PT1
- Do NOT use Heatseeker warning to skip an A/A+ LTP entry

### Target conflict (LTP level vs Heatseeker node at different prices)
- If LTP level gives <0.5R → Heatseeker node wins for PT1
- If both within reasonable R:R → nearer = PT1, farther = PT2
- Always recompute R:R against whichever target you choose

---

## Exception: Heatseeker IS the entry reason

Two setups where Heatseeker is primary AT ENTRY:
1. **King Node Rejection** — King is both the structural anchor AND the entry reason
2. **Gatekeeper Fade** — gatekeeper node is the resistance to fade (1st/2nd test)

In both: the Heatseeker node IS the level. PC still required for trigger timing.

---

## 7 Structural Gaps (identified 2026-06-25)

1. No hard entry domain boundary (Heatseeker kept bleeding into LTP entries)
2. Node interpretation incomplete (direction not specified)
3. Cascade confirmation not connected to KCU grade / sizing
4. No protocol for "Heatseeker says wrong, stop not hit yet"
5. Large negative node = fuel OR wall — not defined by context
6. Reversal entry sequence (Heatseeker signal → then PC) not explicitly ordered
7. Target conflict resolution (LTP level vs Heatseeker node) unresolved

→ See [[Gaps-and-Conflicts]] for full detail.

## Related Notes
- [[LTP-Core]]
- [[Heatseeker-Entry-vs-Target]]
- [[Cascade-Confirmation]]
- [[Common-Traps]]
