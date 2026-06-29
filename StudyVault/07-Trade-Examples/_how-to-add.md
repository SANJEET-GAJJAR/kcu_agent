# How to Add a New Trade to the StudyVault

When a new trade is logged under `~/Desktop/S/setups/TSLA/`, also add it to `_index.md`:

## Step 1 — Add a row to the correct setup table in `_index.md`

```
| TRADE_ID | Date | Ticker | Grade | Key lesson | Full log |
|----------|------|--------|-------|-----------|---------|
| TSLA_20260628_0942_PUTS_LTP_FAILED_RECLAIM_034 | 2026-06-28 | TSLA | A- | Brief lesson in 1 sentence | [[../../../2026-06-28_0942.../Analysis.md]] |
```

## Step 2 — If a new concept or lesson emerged, update the concept note

- New node behavior → update [[Node-Taxonomy]] or [[Node-Direction-Rules]]
- New management rule → update [[Profit-Taking-Rules]] or [[Runner-and-Stop-Management]]
- New model audit entry → update [[Key-Lessons]] and [[Common-Traps]]

## Step 3 — If a candidate pattern reached 3 examples, promote it

- Check [[Cascade-Confirmation]] for patterns at 2/3
- Promote to confirmed when 3rd example is logged
- Add to [[LTP-Trend-Pullback]], [[Rejection-Failed-Reclaim]], etc. as confirmed rule

## Step 4 — Update dashboard after /tutor session

The /tutor skill will auto-update `concepts/` files and `dashboard.md` after each quiz session.

---

## Trade ID Format

`TICKER_YYYYMMDD_HHMM_DIRECTION_SETUP_###`

Examples:
- `TSLA_20260628_0942_PUTS_LTP_FAILED_RECLAIM_034`
- `TSLA_20260629_1005_CALLS_REJECTION_REVERSAL_035`
- `PLTR_20260625_0937_PUTS_LTP_FAILED_RECLAIM_001` (educational)
