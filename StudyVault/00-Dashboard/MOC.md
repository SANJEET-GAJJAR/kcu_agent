---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: all
keywords: MOC, study map, KCU, LTP, Heatseeker, TSLA
---

# KCU x Skylit TSLA — Master Study Map

#dashboard #kcu #ltp #heatseeker

## Overview

Educational backtesting framework for TSLA 0DTE intraday trading.
Core tools: **KCU LTP** (entry backbone) + **Skylit/Heatseeker** (node/target/sizing map).
Not financial advice.

---

## Topic Map

| Section | Key Files | Status |
|---------|-----------|--------|
| **01 — LTP Framework** | [[LTP-Core]], [[LTP-Levels]], [[LTP-Patience-Candle]] | [ ] |
| **02 — Heatseeker** | [[Dealer-Model-Regimes]], [[Node-Taxonomy]], [[Node-Direction-Rules]], [[Node-Distance-Framework]], [[Heatseeker-Entry-vs-Target]] | [ ] |
| **03 — Setup Library** | [[LTP-Trend-Pullback]], [[Rejection-Failed-Reclaim]], [[Rug-Pull-Reverse-Rug]], [[Reversal-Advanced]], [[No-Trade-Conditions]] | [ ] |
| **04 — Trade Management** | [[Profit-Taking-Rules]], [[Runner-and-Stop-Management]], [[Cascade-Confirmation]], [[Invalidation-Rules]] | [ ] |
| **05 — KCU+Heatseeker Integration** | [[Integration-Framework]], [[Gaps-and-Conflicts]] | [ ] |
| **06 — Model Audit Lessons** | [[Key-Lessons]] | [ ] |
| **07 — Trade Examples** | [[_index]] (35 trades) | [ ] |

---

## Practice Files

| Area | Questions | Link |
|------|-----------|------|
| LTP Framework | 10 | [[Practice-LTP]] |
| Heatseeker | 10 | [[Practice-Heatseeker]] |
| Setup Library | 10 | [[Practice-Setups]] |
| Trade Management | 10 | [[Practice-Management]] |
| Integration | 8 | [[Practice-Integration]] |
| Model Audit | 8 | [[Practice-Audit]] |

---

## Tag Index

| Tag | Topic | Hierarchy |
|-----|-------|-----------|
| `#kcu` | KCU framework top level | domain |
| `#ltp` | Levels/Trend/PC | domain → detail |
| `#heatseeker` | Skylit/Heatseeker nodes | domain |
| `#node` | Individual node concepts | detail |
| `#setup` | Trade setup types | domain |
| `#management` | Exit/PT/runner rules | domain |
| `#integration` | KCU+Heatseeker combined | domain |
| `#model-audit` | Documented model misses | domain |
| `#practice` | Practice questions | note-type |
| `#dashboard` | Dashboard/navigation | note-type |

---

## Weak Areas (updated by /tutor)

- [ ] *Run /tutor to identify weak areas — none logged yet*

---

## Non-core Topic Policy

| Source | Content | Handling |
|--------|---------|----------|
| Trade Analysis.md files (individual) | Per-trade operational logs | **Excluded from concept notes** — see [[_index]] for structured examples |
| CLAUDE.md | Project config | **Excluded** — operational, not study content |
| TSLA_Trade_Index.csv | Data rows | **Excluded** — data file |
| storage_test.md, live_trades.md | Operational | **Excluded** |
