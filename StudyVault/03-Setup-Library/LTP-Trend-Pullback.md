---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 7A, kcu_framework.md LTP section
keywords: LTP, trend pullback, continuation, entry, stop, PT1
---

# LTP Trend Pullback ★★★

#setup #ltp

## Setup Definition

Best when: TSLA has clear 2m/5m trend, pulls back in a controlled way, forms a PC near a level, and offers tight invalidation with open path to PT1.

## Entry Rules

| Component | Rule |
|-----------|------|
| Entry | Break of 2m/5m PC in trend direction |
| Stop | Other side of PC (PC high for shorts, PC low for longs) |
| PT1 | First LTP level or Heatseeker node within 2-4 pts |
| Runner | Only when cascade 3-of-3 confirms |

## Quality Checklist

- ✓ Clear trend on 2m (HH/HL for calls, LL/LH for puts)
- ✓ VWAP confirms direction
- ✓ Controlled pullback (not aggressive against trend)
- ✓ PC contained, small range, at or near a level
- ✓ No opposing node blocking PT1 within 0-2 pts
- ✓ R:R ≥ 1.5

## Avoid When

- Pullback volume too strong against trend
- Entry into an opposing node (within 0-2 pts)
- No clear PT1 (blocked or too far)
- PC already failed once today at the same level
- Huge PC range (stop too wide for R:R)

## Failed LTP Tag

When an LTP entry fails to make the expected HH/HL (calls) or LL/LH (puts):
- Tag as FAILED_LTP_WATCH
- Do NOT retry or flip immediately
- Wait for a FRESH confirmed setup
- **FAILED_LTP_ENTRY is not allowed as a strategy** — it is a warning tag only

## Trade Examples (see [[_index]])

- **Trade 018** (TSLA 2026-03-24): A- LTP trend pullback long from fib 0.382 + rising 8 EMA. PT1 hit. Runner gave back via flat BE stop. → [[Runner-and-Stop-Management]]
- **Trade 022** (TSLA 2026-03-24): A LTP calls breakout off 380 King floor. Multi-hour basing, floor-strengthening confirmed. MFE 13.76R.
- **Trade 009** (TSLA 2026-06-18): A- LTP pullback continuation. Fuel loaded before break, King explosive growth.

## Related Notes
- [[LTP-Core]]
- [[LTP-Levels]]
- [[LTP-Patience-Candle]]
- [[Cascade-Confirmation]]
