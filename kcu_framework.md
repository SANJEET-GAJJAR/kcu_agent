# KCU Framework Master Reference for Claude / TSLA Live Trading Session

**File name:** `kcu_framework.md`  
**Purpose:** master local knowledge file for Claude Code / Claude session startup. Use this as the core KCU/LTP framework reference for TSLA backtesting, live chart review, Skylit/Heatseeker interpretation, and discipline alerts.

**Important:** This is educational framework material only. It is not financial advice. Do not auto-trade. Do not generate direct buy/sell commands. Use `WATCH`, `WAIT`, `SKIP`, `NO_TRADE`, `DISCIPLINE_ALERT`, and `MANUAL_CONFIRMATION_REQUIRED` language.

---

## 0. How Claude Should Use This File

At the start of every TSLA live-trading or backtesting session:

1. Load this file first.
2. Treat it as the KCU framework baseline.
3. Also read the user-specific TSLA trading profile at:
   - `~/Desktop/S/setups/TSLA/CLAUDE.md`
   - `~/Desktop/S/setups/TSLA/claude.md`
4. Treat user-specific TSLA instructions as higher priority than generic framework notes when resolving discipline, sizing, ticker focus, and mistake patterns.
5. Use official KCU Indicator docs as context for indicator mechanics and feature behavior, especially patience candle visuals, levels, alerts, timeframes, filters, and no-trade rules.
6. Never invent missing KCU rules. If a strategy’s entry/stop/target is unclear, mark it as unclear and ask for clarification.
7. Separate **confirmed rules**, **partially confirmed rules**, **contradictions**, and **training gaps**.
8. For live trading, classify scenarios conservatively. If unsure, choose `WAIT` or `SKIP`.

---

## 1. Source Priority

Use this priority order:

1. Live market data and chart context provided by the user.
2. Hard safety rules: no auto-trading, no direct orders, no hidden assumptions.
3. User’s TSLA profile file: `~/Desktop/S/setups/TSLA/CLAUDE.md`.
4. This file: `kcu_framework.md`.
5. Official KCU LTP Indicator docs.
6. User’s backtesting files under `~/Desktop/S/setups/` and `~/Desktop/S/sky/`.
7. General trading logic only when explicitly labeled as inference.

---

## 2. Official KCU Indicator Documentation to Reference

Claude should refer to these official docs for indicator feature context:

1. **LTP Indicator - Setup**  
   `https://docs.google.com/document/d/1eaWl5zXAhxBOtiGpzqoSw-Z7uB05mwiyq6rPCT5GZOA/mobilebasic`

2. **LTP Indicator - Features & Settings**  
   `https://docs.google.com/document/d/1E3RThLMuNxxIj-vXFGW68rOE_rT4l3i-OLhmXsgLhf8/mobilebasic`

3. **LTP Indicator - FAQ**  
   `https://docs.google.com/document/d/1qpZGjmh4JZ4AyH_sk4J_qmGSCAZNbBTyUJte_daU4xw/mobilebasic`

### Key official-doc takeaways

- The KCU LTP Indicator is intended for KCU/LTP educational execution, not financial advice.
- The indicator is designed to show the relevant KCU/LTP sub-indicators when needed.
- It intentionally supports only the core KCU timeframes: **2m, 5m, 10m, 1h, and 1D**.
- It visually refreshes each morning. For backtesting prior days, use **TradingView Replay** to see historical indicator visuals accurately.
- Hourly levels are drawn in the morning around **8:30 EST** and should not repaint during the day.
- Premarket levels are drawn from **4:30 EST to 9:30 EST**.
- Opening range levels are based on the **15-minute Opening Range**.
- Some indicator visuals intentionally end or stop triggering after **15:00 EST** because Somesh recommends not trading past 3 PM.
- Indicator setup requires live data and TradingView configuration; alerts must be created manually in TradingView.
- Indicator alerts are based on the settings at the time the alert is created. Changing settings later requires deleting/recreating alerts.
- Patience candle alerts are informational. A PC alert does **not** mean automatic entry.
- Default settings represent required/core indicators; optional settings should be chosen based on backtesting and live trade data.

---

## 3. Official Indicator Feature Map

### 3.1 Level features

The LTP Indicator includes the following level-related features:

- Hourly Levels
- Dynamite Levels
- SPX-specific Dynamite Zones
- SPX Dynamite Levels overlaid on SPY
- Psychological Levels
- All-Time High levels
- Premarket High / Premarket Low
- 15-minute Opening Range High / Low
- Opening Price

#### Hourly Levels

- Drawn fresh daily around **8:30 EST**.
- Intended not to change during the trading day.
- Only a smaller relevant subset is shown to keep charts clean.
- More levels become visible as price moves away from the open.
- For historical review, use TradingView Replay.
- Levels should be used as confluence, targets, invalidation zones, and risk/reward references.

#### Dynamite Levels

- Drawn in the morning and revealed as price moves.
- SPX has special Dynamite handling.
- On SPX, Somesh considers zones around 50-point and 100-point Dynamite Levels:
  - roughly **±2 points** around 50-point increment Dynamite levels
  - roughly **±5 points** around 100-point increment Dynamite levels
- SPX-specific Dynamite behavior may change temporarily depending on how price has recently reacted to these zones.

#### Premarket Levels

- PMH/PML are drawn from 4:30 EST to 9:30 EST.
- They are important for reclaim, rejection, support/resistance, and context.

#### Opening Range

- KCU indicator uses **15-minute Opening Range** levels.
- ORH/ORL can act as breakout, retest, bounce, or rejection zones.

#### Opening Price

- Opening price can be used as a level and sometimes as a target reference.

---

### 3.2 Trend features

The LTP Indicator includes the following trend-related features:

- 200 SMA 1D
- 200 SMA 1h
- 21 EMA 1h
- 200 SMA 10m
- 200 SMA 5m
- 21 EMA 5m
- 8 EMA 5m
- 200 SMA 2m
- VWAP and VWAP Cloud
- Auto Fibonacci Retracement
- Pivot-Based Structure: HH, HL, LL, LH
- No Trading Zone (NTZ)
- Ripster Cloud

#### Moving averages

- The 200 SMA 1D, 1h, 10m, 5m, and 2m represent their own fixed timeframe values regardless of the chart timeframe.
- The 8 EMA 5m and 21 EMA 5m are used as trend context and potential King/Queen confluence.

#### 200 SMA Core Rule — What NOT to Do

The 200 SMA does not tell you what to trade. It tells you what NOT to trade.

- 200 SMA at the top of the chart → do not look for upside moves.
- 200 SMA at the bottom of the chart → do not look for downside moves.

Once you eliminate the wrong direction, trading becomes easier.

**200 SMA timeframe hierarchy (priority order):**

1. **Hourly** — most important, baseline. Always check this first.
2. **5-minute** — second priority, exception layer.
3. **10-minute** — third priority.
4. **2-minute** — least important.

Do not watch 15-minute, 30-minute, or arbitrary timeframes (13m, 37m, etc.). The 200 SMA gets respected on any timeframe — that's noise, not signal.

**How to apply by chart timeframe:**

- Trading on 2m chart → watch 200 SMA on 2m AND 5m.
- Trading on 5m chart → watch 200 SMA on 5m only.
- Trading on 10m chart → watch 200 SMA on 10m only.
- Trading on 1h chart → watch 200 SMA on 1h only (your baseline).

The hourly 200 SMA is the foundation. Everything else builds from it.

#### VWAP and VWAP Cloud

- VWAP can be shown with a transparent VWAP Cloud/zone.
- VWAP is central to Advanced VWAP and King and Queen.
- VWAP can act as dynamic support/resistance, reclaim zone, rejection zone, or confluence.

#### Auto Fibonacci Retracement

- Auto Fib trails price as it trends.
- It shows current/relevant intraday retracement levels.
- It stops trailing after the 50% level is broken and resumes after reset/new HOD/LOD.
- It can be used as a PC Trend Filter.

#### Auto Fibonacci — The 0.5 Rule: Elastic Band Breaks

The 0.5 Fibonacci level is the single most important Fib level for trend validity.

**The Elastic Band Model:**

| Retracement | Elastic Band State | Trade Direction |
|---|---|---|
| 0.236 – 0.382 | Stretched but holding | Still interested in original direction |
| 0.5 | **Snaps. Done.** | Stop looking for original direction |
| Beyond 0.5 | Failed trend | Wait for opposite-direction PC only |

**The Rule:**

> When price pulls back and **touches** the 0.5 Fibonacci level, the trend is no longer valid for continuation plays in the original direction.

- Bullish trend → price pulls back to 0.5 → **do not look for upside plays.**
- Bearish trend → price bounces to 0.5 → **do not look for downside plays.**

What usually happens after 0.5 is hit: price wicks slightly, catches liquidity, then breaks structure and crashes hard in the opposite direction. If you are holding options, you are down 50–60% by the time the real move happens.

**What to do instead:**

- Above 0.5: trend intact. Continue looking for original-direction LTP setups.
- Touches 0.5: trend broken. **Stop.** Wait for a fresh **opposite-direction** patience candle.
- Do not force a reversal immediately after 0.5 is hit. Wait for the PC to form.

**How to calculate 0.5 intraday:**

1. Identify the swing low (or day's low) for an uptrend move.
2. Identify the swing high (HOD) for that move.
3. Range = HOD − Low.
4. 0.5 level = HOD − (Range × 0.5).
5. If price pullback touches or exceeds this level, the trend is invalidated.

**Live assistant rule:**

```text
FIB_0.5_HIT: price has reached or exceeded the 0.5 retracement of the [date] move.
Trend invalidated for [upside/downside] plays. Do not take LTP in original direction.
Wait for fresh opposite-direction PC only.
```

**Backtest note:** Any accepted trade in the original trend direction taken AFTER the 0.5 level is hit should be downgraded to B or flagged as risky, even if it works. The rule protects against the average case where 0.5 hits precede violent reversals.

#### Pivot structure

- The indicator can display HH, HL, LL, LH labels and dotted levels.
- Structure may differ across 2m, 5m, and 10m due to individual candle shapes.
- Structure matters for trend, reversal, and Failed LTP observation.

#### No Trading Zone

- NTZ can show:
  - Premarket H/L range no-trade zone
  - 15m Opening Range no-trade zone
  - Previous Day H/L range no-trade zone
- NTZ is not on by default. Use what Somesh is currently using or what personal backtesting supports.

#### Ripster Cloud

- Ripster Cloud only becomes visible after **13:00 EST**, aligned with the Cloud Strategy.

---

### 3.3 Patience Candle Indicator Features

The LTP Indicator can display:

- Current patience candles
- All triggered patience candles
- Latest triggered patience candle
- All patience candles, triggered or not

Visuals can include arrows and darkened candle colors.

#### Important PC visual meanings

- Yellow arrows denote current/latest patience candles.
- Green arrows denote possible bullish triggered patience candle entries.
- Red arrows denote possible bearish triggered patience candle entries.
- Purple arrows can show all patience candles, whether triggered or not.
- “All Patience Candles” is useful for study/backtesting, not ideal for live trading.
- “Show Only Triggered Patience Candles” is more informative live because it focuses on actionable PCs.

#### PC trigger definition from indicator docs

A triggered PC means the basic patience candle entry condition fired:

- Bullish trigger: the high of a candle whose high is contained within the previous candle’s high gets broken. (Low may exceed prior low — upside containment is what matters for a bullish PC.)
- Bearish trigger: the low of a candle whose low is contained within the previous candle’s low gets broken. (High may exceed prior high — downside containment is what matters for a bearish PC.)

**Full inside bar (both sides contained) = good/clean PC. One-sided containment in the direction of the move = valid PC.**

Important: This does **not** automatically mean a full LTP entry is valid. A PC trigger alone does not account for levels, trend, confluence, R:R, or user discipline.

#### Current PC / 30-second rule

- Current PCs can exist as the current unclosed candle or the prior closed candle.
- The 30-second rule only shows/alerts a current PC once there are 30 seconds left before candle close. This reduces early noise.

#### PC Trend Filters

The indicator can filter patience candles by:

- Auto Fib trend
- Volume
- NTZ
- Premarket Range
- Opening Range
- Previous Day Range
- VWAP
- 21 EMA 5m
- 8 EMA 5m
- EMA Cross

Notes:

- PC filters apply trend/range logic to reduce noisy PC signals.
- Filtered PCs can align better with the visual trend.
- No filter is perfect; filters can remove some ideal entries.
- Filters can be stacked.
- Auto Fib PC Trend Filter is on by default in newer versions and performed well in internal indicator backtests/live trades.

#### Volume filter

- Volume filter only shows PCs that have lower volume than the previous candle.
- This aligns with the extracted training concept: lower volume on PC/pullback can show controlled pause rather than aggressive opposition.

#### PC Approach Filters

- PC Approach Filters filter out patience candles approaching 200 SMAs.
- Core concept: do not take trades directly into 200 SMAs unless there is enough room.
- PCs about **1.5 R:R away from the 200 SMAs** can be filtered out.
- Approach Filters are on by default and should generally remain on unless strong personal backtest/live data says otherwise.

#### PC R:R Guides

- R:R Guides can show target and stop guide lines for current/triggered PCs.
- Target/stop side depends on bullish or bearish PC trigger:
  - Long trigger: target above, stop below.
  - Short trigger: target below, stop above.
- R:R Guides are based only on reward-to-risk distance, not levels, structure, moving averages, or other context.
- Use them as a visual aid, not an automatic trade signal.

---

### 3.4 Timeframe and time-of-day reminders

- Indicator timeframes: **2m, 5m, 10m, 1h, 1D**.
- Timeframe reminder:
  - 10:00 EST on 2m: “Use 5m”.
  - 11:00 EST on 5m: “Use 10m”.
- Stop Trading Reminder:
  - 15:00 EST stop-trading message.
  - Regardless of visual setting, patience candles, some sub-indicators, and alerts do not trigger after 15:00 EST.

User-specific adjustment:

- User focuses heavily on the first 90 minutes, but valid A/A+ TSLA setups after 11:00 should not be automatically rejected. Grade them lower or require stronger confirmation unless clearly clean.
- Avoid trading after 15:00 unless user explicitly wants analysis only.

---

### 3.5 Info Box features

The Info Box can show contextual data:

- Witching days warning/countdown
- Earnings days warning/countdown
- VIX value and VIX range
- SPY/QQQ convergence or divergence
- Relative Strength / Weakness / Even

Definitions:

- SPY/QQQ convergent: both above or both below opening price.
- SPY/QQQ divergent: one above and one below opening price.
- Relative Strength: stock and market moving upward in agreement, and stock has moved more than market.
- Relative Weakness: stock and market moving downward in agreement, and stock has moved more than market.
- Relative Even: stock/market disagree in direction or stock has moved less than/equal to market.

---

## 4. User-Specific TSLA Trading Context

Claude should use these personal rules together with the KCU framework.

### 4.1 Core user goals

- Build a TSLA-specific backtesting and live-trading assistant.
- Use KCU/LTP, Skylit Heatseeker/Atlas, and personal backtests.
- Prefer **first 90 minutes**.
- Do not reject all post-11 setups automatically; grade them lower or require stronger confirmation.
- Wants **1:2 R:R** where possible.
- PT1 based on hourly/key levels, sell partial, keep runner only if justified.
- Not looking for home runs; wants clean, repeatable LTP/rejection plays.
- Wants alerts that prevent TSLA FOMO, oversizing, and front-running.

### 4.2 User recurring mistakes

- FOMO, especially TSLA/NVDA.
- Oversizing favorite tickers.
- Front-running LTP before PC confirmation.
- Taking LTP below/above poor levels.
- Mixing tickers and forcing trades.
- Re-entering after first win/loss.
- Taking trades in chop.
- Taking trades where PT1 is too close or node/level room is poor.
- Ignoring that LTP needs all three: Level + Trend + PC.

### 4.3 Required assistant behavior for live TSLA

Use short, decisive alerts:

- `WATCH`
- `WAIT`
- `SKIP`
- `CHOP_STAY_OUT`
- `DISCIPLINE_ALERT`
- `MANUAL_CONFIRMATION_REQUIRED`

Never say:

- “Buy now.”
- “Short now.”
- “Take X contracts.”
- “This will work.”

Use wording:

- “Watch only.”
- “Need PC break.”
- “Do not front-run.”
- “Manual stop/target confirmation required.”
- “No A setup yet.”

---

## 5. Core KCU Philosophy

KCU/LTP is not about predicting every move. It is about waiting for a high-quality market structure where:

1. There is a meaningful level.
2. Trend is clean and supportive.
3. A patience candle provides an entry trigger and risk reference.
4. Risk/reward is acceptable.
5. The trader avoids chop, FOMO, and partial setups.

The framework is built to manage emotion:

- Levels tell you where the trade matters.
- Trend tells you whether the move has directional support.
- Patience Candle tells you how to enter and where the trade is wrong.
- Profit-taking rules prevent greed.
- No-trade rules prevent boredom trades.

---

## 6. Core Definitions

### LTP

**Levels + Trend + Patience Candle.**  
All three are required. Partial LTP is dangerous.

### Level

A meaningful support/resistance or technical zone where price has reacted or is expected to react. Examples include hourly levels, PMH/PML, PDH/PDL, ORH/ORL, VWAP, EMAs, 200 SMAs, open price, ATH, Dynamite Levels, and psychological levels.

### Trend

The directional behavior of price. Clean trend means clear HH/HL for uptrend or LL/LH for downtrend, supported by volume/market alignment.

### Patience Candle / PC

A small, contained candle after a pullback/pause that gives entry confirmation. A PC is not valid by itself; it must be used with levels, trend, confluence, and R:R.

### PC trigger

- Long trigger: break above PC high.
- Short trigger: break below PC low.

### PC stop logic

- Long PC: stop below PC low.
- Short PC: stop above PC high.

### PC containment

**Minimum (valid PC):** Contained in the direction of the move only.
- Bearish PC: low does not break below the prior candle’s low. High may exceed the prior candle’s high.
- Bullish PC: high does not break above the prior candle’s high. Low may go below the prior candle’s low.

**Full (good/clean PC):** Both high AND low are contained within the prior candle’s range (true inside bar). This is the higher-quality version — tighter stop, better R:R, preferred for A/A+ grading.

The PC should not break the structure on the side that matters for the trade.

### Clean trend

Directional movement with clear structure, good volume, and shallow/manageable pullbacks.

### Messy trend / chop

Overlapping candles, no clean structure, no clear levels, failed breakouts, range-bound movement, mixed signals, or price trapped between nearby levels.

### Rejection

Price approaches/touches a level and moves sharply away. In extracted KCU AI notes, rejection has some source conflict: one answer gave a full rejection guide, later answers said “rejection” was not defined in those training snippets. Treat as usable price-action concept but confirm before calling it a formal KCU strategy.

### Reversal

A trend change after prior trend, weakness, structure break, and PC confirmation. Reversal takes time and requires more than a single rejection candle.

### Failed LTP

A warning/journal tag, not confirmed as a standalone KCU strategy. Use when a valid-looking LTP fails to produce expected continuation. Do not backtest as standalone until instructor clarifies exact entry/stop/target.

### No Trade Zone

A time, range, structure, or condition where trade quality is too poor.

### King and Queen

VWAP is the King. Queens are other technical levels aligned/close to VWAP, creating confluence.

### Advanced VWAP

Long-only extracted strategy built around price coming from below VWAP, forming a PC, closing above VWAP, then entering on the next candle. Market-context rules are contradictory in extracted notes.

### Cloud Strategy

Afternoon strategy using Ripster/Ichimoku Cloud after 13:00 EST, requiring strong morning trend and PC at cloud. Quick scalp, avoid after 15:00.

---

## 7. LTP Framework

### 7.1 L = Levels

Levels come first.

Valid levels:

- Hourly levels
- Daily/weekly levels
- PMH/PML
- PDH/PDL
- ORH/ORL
- Open price
- VWAP
- 8 EMA / 21 EMA / 200 SMA
- Trendlines
- Fibonacci levels
- Dynamite Levels / psychological levels
- Prior support/resistance zones

Good levels:

- Multiple prior reactions.
- Visible on higher timeframes, especially 60m.
- Clean horizontal zone.
- Not too many levels nearby.
- Enough room to next target.

Bad levels:

- One-touch level only.
- Stale or not recently respected.
- Too many nearby levels clustered.
- Level directly at entry blocking reward.
- No clear target.

Rule:

> If levels are clustered and there is no clean reward path, skip.

### 7.2 T = Trend

Trend must be present before PC matters.

Clean uptrend:

- Higher highs and higher lows.
- Pullbacks are shallow.
- Volume supports the move.
- Market/indices align.
- Price respects trendline, VWAP, EMAs, 200 SMA, or structural levels.

Clean downtrend:

- Lower lows and lower highs.
- Bounces are controlled.
- Volume supports downside.
- Market/indices align.

Messy trend:

- Overlapping candles.
- Failed breakouts.
- No clear direction.
- Low volume.
- Conflicting higher/lower timeframe signals.
- Many touches at same level without resolution.

**0.5 Fibonacci trend validity check:**

Before entering any LTP in the original trend direction, verify that price has NOT hit the 0.5 Fibonacci retracement of the current move. If it has, the trend is no longer valid. Skip the trade and wait for an opposite-direction PC.

Rule:

> No clean trend = no LTP. Trend that hit 0.5 Fib = no LTP in that direction.

### 7.3 P = Patience Candle

PC is the entry confirmation and risk reference.

Good PC (A/A+ quality):

- Both high AND low contained within prior candle (full inside bar). Tighter stop, better R:R.
- Small relative to prior candles.
- Forms at meaningful level/confluence.
- Appears after pullback/pause.
- Volume often lower than trend candles or prior candle.

Valid PC (minimum requirement):

- Contained in the direction of the move only.
- Bearish PC: low does not break prior candle's low (high may exceed prior high).
- Bullish PC: high does not break prior candle's high (low may go below prior low).
- Still requires level + trend + R:R check.

Bad PC:

- Breaks containment on the relevant side (bearish PC makes new low / bullish PC makes new high).
- Too large — stop becomes too wide.
- Forms in chop.
- Forms without trend.
- Forms directly into 200 SMA or major level with poor room.
- No clear target.

PC shape:

- Shape is less important than containment and context.
- It can be green/red/doji/wick candle.
- What matters: trend + level + directional containment + trigger.

### 7.4 Entry and stop rules

Long LTP:

- Level below/at support or reclaim zone.
- Clean uptrend.
- PC forms.
- Entry trigger: break above PC high.
- Stop: below PC low.
- Target: next level / structure / R:R guide / PT1.

Short LTP:

- Level above/at resistance or breakdown zone.
- Clean downtrend.
- PC forms.
- Entry trigger: break below PC low.
- Stop: above PC high.
- Target: next level / structure / R:R guide / PT1.

### 7.5 Partial LTP warning

Partial LTP is dangerous.

Do not take trades with only:

- Level + PC but no trend.
- Trend + PC but no meaningful level.
- Level + Trend but no PC.

Assistant alert:

> Partial LTP detected. Level, trend, and PC are not all aligned. Skip.

---

## 8. Patience Candle Rules

### 8.1 Extracted PC rules

ABCD pattern:

- A: prior candle / prior move.
- B: pullback candle.
- C: patience candle.
- D: breakout/trigger.

Core rules:

1. PC must be contained in the direction of the move (minimum). Full inside bar = better quality.
2. Smaller is better.
3. Volume on PC/pullback should often be lighter.
4. PC must appear after level/trend context is established.
5. PC gives entry and stop structure.
6. Bearish PC: low contained (doesn't break prior low) — high may exceed prior high. Short trigger = break of PC low.
7. Bullish PC: high contained (doesn't break prior high) — low may go below prior low. Long trigger = break of PC high.

### 8.2 Live trading PC rule

Do not enter only because the indicator shows a PC arrow.

PC arrow means:

- a possible PC trigger happened;
- not necessarily a full LTP entry.

Full LTP requires:

- level
- trend
- PC
- confluence
- R:R
- no no-trade condition

### 8.3 PC failure rule

If a PC fails once at the same level, do not repeatedly retry the same setup.

Assistant alert:

> PC already failed once at this level. Do not retry the same LTP. Wait for fresh structure.

---

## 9. Strategy Library

## 9.1 Advanced VWAP

### Source status

- Usable strategy.
- Entry/stop/target rules mostly clear.
- Market context is contradictory in extracted KCU AI notes.
- Use as `CONFIDENCE: MEDIUM` until instructor clarifies ideal market context.

### Confirmed extracted rules

- Long-only in extracted training.
- Built around retail psychology: many traders see price above VWAP as bullish and buy aggressively.
- Price must come from **below VWAP**.
- PC forms around VWAP.
- PC closes **above VWAP**.
- Entry: next candle after PC closes above VWAP.
- Stop:
  - below PC low, or
  - below VWAP if PC is too large/wide.
- Targets:
  - intraday support/resistance levels,
  - open price print,
  - prior intraday high/structure.
- Requires active management.
- Avoid before first 10–15 minutes after open.
- Avoid after 15:00.

### Contradiction

Extracted notes say both:

- Advanced VWAP works in chop and not strong trends.
- Advanced VWAP requires a trendy stock / trend.

Conservative interpretation for assistant:

> Use Advanced VWAP only for controlled VWAP reclaim/pullback environments. Avoid random chop around VWAP and avoid runaway one-direction trend where VWAP is far behind price.

### Valid context

- Price below VWAP.
- Market not chaotic.
- Stock has directional context.
- Price approaches VWAP from below in controlled manner.
- PC forms near VWAP.
- PC closes above VWAP.
- There is room to target.

### Invalid context

- Candle closes at VWAP but not above.
- No PC.
- PC too large.
- Price in random chop around VWAP.
- Price too far extended.
- No intraday target.
- After 15:00.

### Alert examples

- `Advanced VWAP watch: price came from below VWAP and PC is forming. Need close above VWAP, then next candle confirmation. Do not front-run.`
- `Skip Advanced VWAP: price is chopping around VWAP with no clean reclaim. No A setup.`
- `Advanced VWAP context unclear: training has trend/chop contradiction. Treat as watch only unless controlled reclaim is clean.`

---

## 9.2 King and Queen

### Source status

- Usable strategy.
- Confidence: medium-high.
- Requires PC and trend.

### Core concept

- King = VWAP.
- Queen = any meaningful technical level aligned/visually close to VWAP.

Queens can include:

- 8 EMA
- 21 EMA
- ORB levels
- 200 SMA
- Open price
- Hourly levels
- Previous support/resistance
- Any strong chart level

### Setup

- VWAP and Queen level converge at similar price zone.
- Price approaches confluence.
- Zone acts as “do not disturb” area.
- Must wait for PC at the confluence zone.
- PC is mandatory because market conditions evolved; entering only because King/Queen exists can get blown through.

### Closeness

- Exact price match not required.
- Levels should be visually close.
- Extracted SPY example: 15–20 cents can be acceptable on SPY.
- For other tickers, adapt zone size based on price/volatility; do not blindly use SPY cents.

### Required context

- Some trend must be present.
- Choppy trendless market = weak move.
- PC confirmation required.

### Entry

- Wait for PC around King/Queen zone.
- Enter only on PC break in direction of intended trade.

### Stop

- Use PC-based stop logic unless instructor-specific notes say otherwise.

### Target

- Next level / structure / hourly level / HOD/LOD depending direction.

### Skip

- No PC.
- No trend.
- VWAP and Queen not close enough.
- Too many nearby levels.
- Price blows through confluence.
- R:R poor.

### Alert examples

- `King and Queen watch: VWAP and 8 EMA are aligned. Need PC at zone before entry. No PC = no trade.`
- `Skip King and Queen: confluence exists but trend is messy. Wait.`

---

## 9.3 Rejection Strategy

### Source status

- Source-conflicted.
- One KCU AI response gave a full guide; later response said rejection not covered in that training context.
- Use as price-action concept with caution.
- Do not over-label as official KCU standalone unless user notes/instructor confirm.

### Core concept

Rejection occurs when price approaches/touches a critical level and sharply moves away.

### Rejection vs pullback

- Rejection: sharp move away from level, conviction, often wick + close away.
- Pullback: slower consolidation/grind, less conviction.

### Rejection vs reversal

- Rejection can be a level reaction without full trend change.
- Reversal requires prior trend, weakness, structure break, and PC.
- Do not call reversal from a single rejection candle.

### Requirements from extracted guide

- Critical level.
- Clean trend or meaningful market context.
- Rejection candle/wick or candle closing away from level.
- Patient candle after rejection before entry.
- Volume can matter: increase on rejection, lower volume pullback.
- Overall market direction matters.
- No major blocking level before target.

### Entry

- Do not enter on rejection candle itself.
- Wait for PC after rejection.
- Enter on PC break in intended direction.

### Stop

- Upside bounce/rejection: stop below rejection candle low or PC low depending setup.
- Downside rejection: stop above rejection candle high or PC high.
- Confirm with user/instructor if exact rejection stop is required.

### Target

- Next hourly or critical level.
- Price moves level-to-level.

### Skip

- Choppy premarket.
- Overall market against trade.
- Trend not clean.
- No PC.
- Blocking level close by.
- Seeing what you want to see / confirmation bias.

### Alert examples

- `Rejection watch: price rejected key level. Need follow-up PC before entry. Do not enter on rejection candle.`
- `Skip rejection: level reaction exists but market direction is against trade and target is blocked.`

---

## 9.4 Reversal Strategy

### Source status

- Mostly confirmed.
- Stop logic now clarified.
- Entry timing still somewhat medium confidence.

### Core meaning

Reversal is a turnaround in price movement after prior trend weakens and structure breaks.

### Reversal requires

1. Prior trend.
2. Critical level / zone.
3. Momentum weakness.
4. Volume shift.
5. Structure break.
6. PC after structure break / at critical level.
7. PC break in reversal direction.

### Reversal is not

- A single rejection candle.
- A quick bounce.
- Catching a top/bottom without structure.
- An incomplete structure.

### Market structure types

- Pullback Structure: HH → pullback → HL → HH.
- Breakdown Structure: LL → bounce → LH → LL.
- Incomplete Structure: no confirmed HH/HL or LL/LH yet. Do not trade reversals from incomplete structure.

### Momentum / volume logic

- Price up + volume up = strong uptrend; no reversal yet.
- Price down + volume down = strong downtrend; no reversal yet.
- Price up + volume down = weak uptrend; possible bearish reversal signal.
- Price down + volume up = weak downtrend; possible bullish reversal signal in extracted notes, but be careful and confirm context.

### Bearish reversal after uptrend

- Prior trend: uptrend with HH/HL.
- Structure weakens or breaks down.
- PC forms after failure/at critical level.
- Entry direction: break below PC low.
- Stop: above PC high.
- Target: next support/hourly level/structure; exact target rules less detailed.

### Bullish reversal after downtrend

- Prior trend: downtrend with LL/LH.
- Structure weakens or breaks up.
- PC forms after failure/at critical level.
- Entry direction: break above PC high.
- Stop: below PC low.
- Target: next resistance/hourly level/structure; exact target rules less detailed.

### Confirmed stop rule

Stop goes on the opposite side of the PC:

- Bearish reversal short: stop above PC high.
- Bullish reversal long: stop below PC low.

### Still unclear

- Exact entry timing: PC close vs next candle break.
- Which PC to use if multiple PCs form.
- Worked examples with coordinates not provided.

### Alert examples

- `Reversal watch only: prior trend weakened and structure broke. Need PC break in reversal direction. Stop should be opposite side of PC.`
- `Do not call reversal early: one rejection candle is not enough. Need structure break + PC.`

---

## 9.5 Failed LTP

### Final status

Failed LTP is **not confirmed as a standalone KCU strategy** in the extracted training materials.

Use it as:

- Warning state.
- Journal tag.
- Discipline classifier.

Do not use it as:

- Standalone entry strategy.
- Fully backtestable setup with fixed entry/stop/target.
- Automated live signal.

### Confirmed concept

A valid LTP appears to form but fails to produce expected continuation:

- Uptrend LTP fails to make expected higher high.
- Downtrend LTP fails to make expected lower low.
- Price attempts a level and closes back inside.
- Structure fails.

### Confirmed behavior

- Do not keep forcing original LTP thesis.
- Do not immediately flip.
- Wait for a fresh setup.
- Fresh opposite-direction PC may create reversal-style opportunity, but exact naming/rules are not defined.

### Not covered

- Formal Failed LTP definition as named strategy.
- Exact entry.
- Exact stop.
- Exact PT1.
- Difference from rejection/reversal.
- Worked examples.

### Live assistant use

Use:

- `FAILED_LTP_WATCH`
- `DISCIPLINE_ALERT`

Avoid:

- `FAILED_LTP_ENTRY`

### Alert examples

- `Failed LTP watch: original LTP failed to make expected continuation. Do not retry or flip immediately. Wait for fresh PC/setup.`
- `Skip: same PC failed once at this level. Do not keep retrying.`

---

## 9.6 ORB: Opening Range Breakout

### Source status

- Partially covered.
- ORB Bounce/Reject more covered than pure ORB.

### Core concept

- ORB = Opening Range Breakout.
- KCU indicator provides 15m Opening Range levels.
- OR High / OR Low become important levels.

### Interpretation

- Break and continuation = trend may be developing.
- Break and return into range = chop / failed breakout.

### Pure ORB gaps

Need clarification:

- Exact entry timing.
- Stop placement.
- PT1.
- Whether PC required.
- Invalidation.

### Live assistant rule

Do not trade pure ORB as standalone unless user confirms exact rules. Use ORB as context/level and prefer ORB Bounce/Reject with PC.

---

## 9.7 ORB Bounce / ORB Reject

### Source status

- Covered enough for assistant watch logic.

### Core concept

After price breaks ORB, it retests ORB level.

- Bounce: price respects ORB and continues in breakout direction.
- Reject: price fails/rejects ORB and moves away.

### Requirements

- ORB breakout first.
- Retest of ORB level.
- PC at ORB level.
- Confluence: ORB + PC.
- Intraday/hourly target levels.

### Entry

- Entry uses PC logic at ORB retest.

### Stop

- Based on PC, but exact side follows bullish/ bearish PC logic.

### Target

- Intraday levels / hourly levels.

### Skip

- No PC at ORB.
- No confluence.
- Breakout fails immediately and returns to range.
- No target level.

### Alert examples

- `ORB retest watch: price broke ORH and is retesting. Need PC at ORH for bounce. No PC = no trade.`
- `ORB reject watch: price failed ORH and returned into range. Wait for PC before downside idea.`

---

## 9.8 Cloud Strategy

### Source status

- Mostly covered.
- Stop placement implied, not fully confirmed.

### Core concept

Afternoon strategy using Ripster / Ichimoku Cloud after strong morning trend.

### Confirmed rules

- Cloud appears after 13:00 EST.
- Use after 1 PM ET.
- Avoid after 3 PM ET.
- Requires strong morning trend.
- Price returns to cloud.
- Bounce/rejection from cloud.
- PC forms at cloud.
- Quick scalp: 10–15 minutes.
- Target: HOD or nearby structure/resistance.

### Stop

- Not explicitly covered. Implied below/above bounce/rejection candle or PC.
- Mark `STOP_LOGIC_CONFIDENCE: LOW/MEDIUM`.

### Skip

- Before 1 PM.
- After 3 PM.
- No strong morning trend.
- Morning chop.
- No PC at cloud.
- Holding too long.

### Alert examples

- `Cloud Strategy watch: strong morning trend and price is testing cloud after 1 PM. Need PC at cloud. Quick scalp context only.`
- `Skip Cloud: no strong morning trend or after 3 PM.`

---

## 9.9 Profit Taking Strategy

### Source status

- Covered with one conflict.

### Confirmed rules

- Take profits systematically.
- Use visual estimate of move.
- First profit can be around 50% of move.
- Continue taking profits at hourly levels.
- Final target can be HOD/LOD or next major resistance/support.
- If price action turns ugly/choppy, take profits faster.
- Use hourly structure levels.

### Conflict

Extracted answer says stop loss does **not move** and remains fixed. User’s KCU execution often uses PT1 → sell half → move rest to BE.

Status:

- `PROFIT_TAKING_SOURCE_STATUS: COVERED_WITH_CONFLICT`
- Need clarification whether stop movement depends on strategy/personal method.

### Conservative assistant rule

- Never assume runner should be held.
- Suggest: “PT1 at next level; runner only if trend remains clean.”
- If user’s stored rule says move runner to BE after PT1, follow user-specific profile unless instructor clarification overrides it.

### Alert examples

- `PT1 approaching next hourly level. Consider partials per plan; runner only if trend remains clean.`
- `Price action getting ugly after entry. Protect gains; do not hold for fantasy target.`

---

## 9.10 Stock Selection / Niche Focus

### Source status

- Covered.

### Core concept

Trade a focused basket repeatedly instead of chasing random names.

Extracted training:

- Instructor trades 9 names.
- Avoid scanning hundreds of names.
- Build familiarity.
- Do not add random hot tickers.

User-specific application:

- Focus TSLA and user’s chosen core list.
- For TSLA live agent, stay TSLA-specific unless user explicitly asks multi-ticker.
- Avoid random desk trades.

### Alert example

- `Discipline alert: this is outside your focus list / not TSLA plan. Avoid random ticker FOMO.`

---

## 9.11 No Trade Zones / How Not To Trade

### Source status

- Covered and important.

### Time-based no-trade zones

- Before 9:45 AM: open chop risk.
- Lunch 11:30 AM–1:00 PM: lower volume/chop risk.
- After 3:00 PM: stop trading; indicator also stops PC/sub-indicator alerts after 15:00.

User-specific nuance:

- User focuses first 90 minutes.
- A/A+ trades after 11 can be considered but require stronger confirmation.
- After 3 PM should be analysis-only unless user explicitly overrides.

### Price-action no-trade zones

- No clean trend.
- Ugly/choppy candles.
- Consolidation with no clear breakout/breakdown.
- Price trapped between levels.
- No support/resistance nearby for target.
- Too many nearby levels.
- PC too large.
- PC into 200 SMA / poor R:R.
- No PC.
- Partial LTP.
- Random VWAP chop.
- **0.5 Fibonacci level hit** — trend invalidated. No LTP in original direction until fresh structure forms.

### 200 SMA direction filters

- Long below 200 SMA is lower quality / no-trade depending context.
- Short above 200 SMA is lower quality / no-trade depending context.
- PC Approach Filters are designed to filter PCs approaching 200 SMAs with insufficient room.

### Alert examples

- `No trade zone: price is between levels and trend is unclear. Wait for clean level + trend + PC.`
- `Skip: PC points into 200 SMA with poor room. R:R not there.`
- `Stop trading reminder: after 3 PM. No new trades.`

---

## 9.12 SPX Dynamite Rejection

### Source status

- Not fully extracted from KCU AI.
- Official indicator docs confirm SPX-specific Dynamite Zones exist and are treated differently.
- SPX Dynamite zone widths:
  - ±2 points on 50-point increment Dynamite Levels.
  - ±5 points on 100-point increment Dynamite Levels.
- Need instructor/KCU AI strategy rules for exact rejection setup.

### Live assistant behavior

Do not generate SPX Dynamite Rejection trade logic until extracted. Use as context only:

- SPX at/near Dynamite Zone.
- Watch for rejection/PC/market context.
- Manual confirmation required.

---

## 10. Strategy Confidence Matrix

| Strategy / Concept | Status | Use in live assistant | Use in backtesting |
|---|---|---|---|
| LTP | Confirmed | Yes | Yes |
| Patience Candle | Confirmed | Yes, with filters/context | Yes |
| Advanced VWAP | Partially contradictory | Watch only unless clean controlled reclaim | Yes, but tag contradiction |
| King and Queen | Mostly confirmed | Yes, with PC required | Yes |
| Rejection | Source-conflicted | Watch only / price-action concept | Yes, but tag source conflict |
| Reversal | Mostly confirmed | Yes, with structure + PC | Yes |
| Failed LTP | Not formal standalone | Warning/journal tag only | Do not backtest as standalone |
| ORB | Partially covered | Context / level | Partial |
| ORB Bounce/Reject | Covered enough | Yes, with PC | Yes |
| Cloud Strategy | Mostly covered | Watch after 1 PM, quick scalp context | Yes, stop gap tagged |
| Profit Taking | Covered with conflict | Use conservative PT1/runners | Yes, tag BE conflict |
| Stock Selection | Confirmed | Discipline filter | Yes |
| No Trade Zones | Confirmed | Hard filters | Yes |
| SPX Dynamite Rejection | Not fully extracted | Context only | Needs extraction |

---

## 11. TSLA + Skylit / Heatseeker Live Agent Rules

### 11.1 Role of Skylit/Heatseeker

Use Heatseeker/Atlas node values as **context and target/support/resistance guidance**, not as standalone trade triggers.

For continuation/LTP trades:

- LTP/trend decides go/no-go.
- Heatseeker helps guide PT1, stall zones, runner targets, invalidation, sizing confidence.

For rejection/reversal trades:

- Heatseeker/Atlas can carry more weight because local node reaction matters.
- Still require chart confirmation and KCU logic.

### 11.2 Node tracking concepts

Track:

- Largest positive nodes.
- Largest negative nodes.
- Nearest node above spot.
- Nearest node below spot.
- Node delta over 5s / 30s / 1m / 5m.
- Upside nodes growing.
- Downside nodes growing.
- Support node weakening.
- Resistance node weakening.
- Negative node expanding near spot.
- Price trapped between nearby nodes.

### 11.3 Scenario hierarchy

Use deterministic classification before LLM wording.

Scenarios:

- `LTP_UPSIDE_FORMING`
- `LTP_DOWNSIDE_FORMING`
- `ADVANCED_VWAP_WATCH`
- `KING_AND_QUEEN_WATCH`
- `REJECTION_WATCH`
- `REVERSAL_WATCH`
- `FAILED_LTP_WATCH`
- `ORB_BOUNCE_REJECT_WATCH`
- `CLOUD_STRATEGY_WATCH`
- `CHOP_STAY_OUT`
- `NO_TRADE`
- `DISCIPLINE_ALERT`
- `MANUAL_CONFIRMATION_REQUIRED`

Priority order:

1. `DISCIPLINE_ALERT`
2. `NO_TRADE`
3. `CHOP_STAY_OUT`
4. `REVERSAL_WATCH`
5. `REJECTION_WATCH`
6. `FAILED_LTP_WATCH`
7. `LTP_UPSIDE_FORMING` / `LTP_DOWNSIDE_FORMING`
8. `ADVANCED_VWAP_WATCH`
9. `KING_AND_QUEEN_WATCH`
10. `ORB_BOUNCE_REJECT_WATCH`
11. `CLOUD_STRATEGY_WATCH`

### 11.4 Alerts must be short

Max 60 words when live.

Good style:

- `TSLA LTP watch: reclaim above 397.5. Need PC close/break and room to 400. Do not front-run.`
- `TSLA chop: trapped between 395 and 397.5. Nodes mixed. No A setup. Wait.`
- `TSLA rejection watch: 397.5/400 acting as ceiling. Need failed reclaim + downside PC.`
- `TSLA Failed LTP watch: long idea failed to make HH. Do not flip yet. Need fresh downside PC.`
- `TSLA discipline alert: move already happened. Do not chase. Wait for retest or next clean PC.`

---

## 12. Backtesting Templates

### 12.1 General KCU trade template

```markdown
# KCU Backtest

Backtest ID:
Date:
Ticker:
Time:
Direction:
Setup Type:
Strategy:
Market Context:

## Level
Level used:
Why this level mattered:
Was level clean?:
Nearby blocking levels?:

## Trend
Trend direction:
Was trend clean or messy?:
Trend evidence:
SPY/QQQ alignment:
Relative strength/weakness:

## Indicator Context
Timeframe:
LTP Indicator features visible:
PC arrow type:
PC filter used:
Nearby 200 SMA?:
VWAP / VWAP Cloud:
Auto Fib context:
NTZ present?:

## Patience Candle
Was there a PC?:
PC candle time:
PC quality:
Contained?:
Small/tight?:
Volume lower than previous?:
Was entry before or after PC trigger?:

## Entry
Entry trigger:
Entry price:
Was this a chase?:
Was this front-run?:
Was this partial LTP?:

## Risk
Stop:
Stop reason:
Risk amount:
Was stop PC-based?:
Was stop too wide?:
R:R to PT1:

## Targets
PT1:
PT1 reason:
Runner target:
Runner management:
Did price action get ugly?:

## Result
Win/Loss/BE:
Did PT1 hit?:
Did runner work?:
Exit reason:

## Review
Was this true KCU/LTP?:
Was this chop?:
Was this A+, A, B, C, or no-trade?:
What worked:
What failed:
Main lesson:
Rule to update:
```

### 12.2 Reversal template

```markdown
# Reversal Backtest

Prior trend:
Structure before reversal:
Critical level:
Momentum weakness evidence:
Volume shift evidence:
Structure break:
PC after structure break?:
Entry direction:
PC high:
PC low:
Entry trigger:
Stop opposite side of PC?:
Target reference:
Invalidation:
Was this actually rejection instead?:
```

### 12.3 Failed LTP journal tag template

```markdown
# Failed LTP Observation

Original setup direction:
Level:
Trend:
PC:
Why it looked valid:
What failed to happen:
Did it fail to make HH/LL?:
Did price close back inside level?:
Was there fresh opposite PC?:
Did I retry same setup?:
Did I flip too early?:
Classification: FAILED_LTP_WATCH only
Should this be backtested as standalone?: No, until clarified.
```

---

## 13. Backtesting Tags

Use these tags consistently.

### Core

- `VALID_LTP`
- `PARTIAL_LTP`
- `INVALID_LTP`
- `LEVEL_GOOD`
- `LEVEL_CLUSTERED`
- `TREND_CLEAN`
- `TREND_MESSY`
- `PC_VALID`
- `PC_TOO_LARGE`
- `PC_FAILED_ONCE`
- `BAD_RR`
- `NO_TRADE`

### Strategy

- `ADVANCED_VWAP`
- `VWAP_RECLAIM`
- `VWAP_REJECTION`
- `KING_AND_QUEEN`
- `REJECTION_WATCH`
- `REVERSAL`
- `BEARISH_REVERSAL`
- `BULLISH_REVERSAL`
- `FAILED_LTP_WATCH`
- `ORB`
- `ORB_BOUNCE`
- `ORB_REJECT`
- `CLOUD_STRATEGY`
- `PROFIT_TAKING`
- `STOCK_SELECTION_DISCIPLINE`
- `NTZ`

### Indicator/context

- `PC_TREND_FILTER`
- `PC_APPROACH_FILTER_200SMA`
- `AUTO_FIB_FILTER`
- `FIB_0.5_HIT` — trend invalidated, price touched 0.5 retracement
- `FIB_0.382_BOUNCE` — price held at 0.382, trend still intact
- `FIB_0.5_RISKY` — trade taken after or near 0.5 hit, flag as elevated risk
- `VWAP_FILTER`
- `OPENING_RANGE_FILTER`
- `PM_RANGE_FILTER`
- `NTZ_FILTER`
- `R_R_GUIDE`
- `SPY_QQQ_CONVERGENCE`
- `SPY_QQQ_DIVERGENCE`
- `RELATIVE_STRENGTH`
- `RELATIVE_WEAKNESS`

### Mistakes

- `FOMO`
- `CHASE`
- `FRONT_RUN_PC`
- `OVERSIZED_FAVORITE_TICKER`
- `REENTRY_AFTER_WIN`
- `REVENGE_TRADE`
- `TRADED_CHOP`
- `IGNORED_LEVEL`
- `IGNORED_TREND`
- `IGNORED_PC`
- `NO_TARGET`
- `HOLD_RUNNER_WITHOUT_REASON`

---

## 14. Grading System

### A+ setup

- Clean level.
- Clean trend.
- Tight PC.
- Strong confluence.
- R:R >= 2 preferred.
- No nearby blocking levels.
- Market alignment.
- Fits first 90 minutes or very clean later context.
- No no-trade condition.

### A setup

- Level/trend/PC all valid.
- One minor imperfection.
- R:R acceptable.
- Good target.

### B setup

- Partial uncertainty.
- Later time window.
- Slightly messy trend or less clean level.
- Smaller size or watch only.

### C setup

- Too many questions.
- Choppy.
- Poor R:R.
- Avoid.

### No-trade

- Missing level, trend, or PC.
- Price trapped between levels/nodes.
- PC into 200 SMA / no room.
- Failed PC already.
- Move already happened.
- After 3 PM.

---

## 15. Remaining Gaps to Keep Marked

### Advanced VWAP

- Ideal market context contradictory: chop vs trend vs controlled reclaim.
- Ask instructor: “Is Advanced VWAP best in controlled VWAP reclaim conditions rather than random chop or runaway trend?”

### Profit Taking

- Conflict: extracted training says stop stays fixed; user’s system often uses PT1 → runner to BE.
- Ask instructor: “After PT1, does stop remain fixed or move to breakeven? Does it depend on setup?”

### Cloud Strategy

- Stop logic not explicitly confirmed.
- Ask instructor: “Is Cloud Strategy stop based on PC, cloud break, bounce candle, or structure?”

### Pure ORB

- Exact ORB breakout stop/target/PC requirements are incomplete.

### Rejection

- Source conflict: one guide detailed it; later response said not covered.
- Ask: “Is Rejection an official KCU strategy or a general price-action concept?”

### SPX Dynamite Rejection

- Need full strategy extraction.
- Official docs confirm SPX Dynamite Zones but not full rejection playbook.

### Failed LTP

- Not formal standalone.
- Keep as warning/journal tag only.

---

## 16. Claude Live Session Rules

When Claude reviews a TSLA chart live:

1. Start with state classification, not explanation.
2. Check no-trade conditions first.
3. Check levels.
4. Check trend.
5. Check PC.
6. Check R:R to nearest level/node.
7. Check Heatseeker/Skylit node support.
8. Check user-specific mistakes: FOMO, oversizing, front-running, re-entry.
9. Output max 3 short bullets.
10. Avoid long essays while live.

Output format:

```text
STATE: WATCH / WAIT / SKIP / CHOP / DISCIPLINE_ALERT
SETUP: LTP / REJECTION / REVERSAL / ADVANCED_VWAP / KING_AND_QUEEN / NONE
REASON: one sentence
TRIGGER NEEDED: PC break / reclaim / loss of level / none
INVALIDATION: key level or PC opposite side if known
```

If unclear:

```text
STATE: WAIT
REASON: KCU confirmation incomplete. Need Level + Trend + PC.
```

---

## 17. Example Live Responses

### Good LTP watch

```text
STATE: WATCH
SETUP: LTP_UPSIDE_FORMING
REASON: Level and trend align, PC forming near support. Need break above PC high.
TRIGGER NEEDED: PC high break with room to PT1.
INVALIDATION: PC low / level loss.
```

### Chop

```text
STATE: CHOP_STAY_OUT
SETUP: NONE
REASON: Price is between levels/nodes and candles overlap. No clean trend.
TRIGGER NEEDED: Clean reclaim or loss of range.
INVALIDATION: N/A
```

### Reversal watch

```text
STATE: WATCH
SETUP: REVERSAL_WATCH
REASON: Prior trend weakened and structure broke. Need PC in reversal direction.
TRIGGER NEEDED: Break of PC in reversal direction.
INVALIDATION: Opposite side of PC.
```

### Failed LTP warning

```text
STATE: DISCIPLINE_ALERT
SETUP: FAILED_LTP_WATCH
REASON: Original LTP failed to continue. Do not retry or flip immediately.
TRIGGER NEEDED: Fresh opposite-direction setup.
INVALIDATION: N/A
```

### Advanced VWAP watch

```text
STATE: WATCH
SETUP: ADVANCED_VWAP
REASON: Price came from below VWAP and PC is near reclaim. Market-context rule is partially contradictory, so require clean controlled reclaim.
TRIGGER NEEDED: PC close above VWAP + next candle confirmation.
INVALIDATION: Below PC/VWAP.
```

---

## 18. Implementation Notes for Claude Code / Codex

When building the live agent:

- Use deterministic rule engine first.
- LLM only formats short alerts.
- Store strategy confidence and source status for every classification.
- Do not call a setup tradable if source status is unclear.
- For Failed LTP, do not generate entries.
- For SPX Dynamite Rejection, do not generate entries until extracted.
- For Advanced VWAP, include `market_context_confidence: low`.
- For Rejection, include `source_conflict: true` unless user confirms it.
- For Reversal, use PC opposite-side stop rule.
- For No Trade Zones, treat them as hard filters.
- For PC indicator arrows, remember they are not automatic LTP entries.
- For PC trend filters, note that filtered PCs may reduce noise but can filter out good trades.
- For approach filters, do not take PCs pointing into 200 SMA without enough room.
- For R:R guides, use them only as risk visualization, not full target logic.

Recommended scenario object:

```json
{
  "state": "WATCH | WAIT | SKIP | CHOP_STAY_OUT | DISCIPLINE_ALERT",
  "setup": "LTP_UPSIDE_FORMING | REVERSAL_WATCH | ...",
  "source_status": "CONFIRMED | PARTIAL | CONFLICTED | UNCLEAR",
  "confidence": 0.0,
  "requires_manual_confirmation": true,
  "entry_condition": "...",
  "stop_logic": "...",
  "target_logic": "...",
  "reason": "...",
  "risk_warning": "..."
}
```

---

## 19. Final Non-Negotiables

- Do not front-run PC.
- Do not use partial LTP.
- Do not trade chop.
- Do not chase TSLA after move already happened.
- Do not retry a failed PC at the same level.
- Do not treat PC arrow as automatic entry.
- Do not trade directly into 200 SMA / major level with poor R:R.
- Do not overrule no-trade zones because TSLA is moving.
- Do not generate auto-trade instructions.
- Do not call uncertain strategies confirmed.
- When in doubt: `WAIT` or `SKIP`.

---

## 20. Quick Startup Prompt for Claude Session

Use this in `CLAUDE.md` or at the top of the Claude TSLA session:

```text
Read `kcu_framework.md` first. Use it as the KCU/LTP framework source of truth for this TSLA session. Also read `~/Desktop/S/setups/TSLA/CLAUDE.md` if present for my personal TSLA trading profile.

When analyzing live TSLA charts, be concise and conservative. Classify state first: WATCH, WAIT, SKIP, CHOP, DISCIPLINE_ALERT. Use KCU order: Levels → Trend → Patience Candle → R:R → Heatseeker/Skylit context. Do not front-run PCs. Do not treat PC arrows as automatic entries. Do not call Failed LTP a standalone entry strategy. Always mark unclear rules as manual confirmation required.
```
