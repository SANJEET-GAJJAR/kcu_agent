# CLAUDE.md — TSLA KCU x Skylit Backtesting Project (v2)

Scope: TSLA only, 0DTE, intraday. Educational backtesting. Not financial advice.
Project root: `~/Desktop/s/setups/TSLA`. Write ONLY under `~/Desktop/s/setups/TSLA/**`. Never write outside without explicit approval.
Owner: Sunny. Mode default: Backtest. Storage: LOCAL (you have write access — actually save files; confirm with storage_test.md at session start).

---

## Session start
1. `pwd`, confirm root. 2. Write/verify storage_test.md ("TSLA local storage is working."). 3. `ls`. 4. Read this file + TSLA playbook PDF + master files. 5. One-line understanding confirm. 6. Confirm mode. 7. Before starting any backtesting for the day, ask Sunny for premarket context: the 09:29 chart + his subjective feel/read of the premarket. Hypothesis (2026-06-23, untested): premarket character may predict morning/afternoon chop — tag as HYPOTHESIS until 3+ days show the same correlation. Don't grade until confirmed.

## Operating principles
- Low-token. No fluff, no repeated theory, no generic advice. Execution-focused.
- Never claim a file saved unless written. Prefer `unknown` over guessing; candidate-pattern over false certainty; no-trade over forced trade; revision over preserving wrong analysis.
- Track my misses AND yours. Direct accountability, no deflection. Root-cause and update playbook.
- A trade winning despite weak/absent price-action or Heatseeker support is an outcome, not validation. Grade the setup quality on what was actually there at entry, independent of the result — a risky or out-of-thesis trade working once does NOT mean the same setup will work again, and must not be logged as a confirmed pattern or used to raise confidence in repeating it. Log it explicitly as "worked despite poor/no setup" (lucky/anomalous), kept separate from real candidate-pattern examples — this is the bad-learning-behavior trap.

## Framework (confirmed)
- **LTP (Levels, Trend, Patience Candle) = price-action backbone. Decides go/no-go.**
- **Skylit/Heatseeker = node/target/wall/sizing map.** Primary for rejection/reversal (local reaction IS the trade). Secondary for continuation (PT1, stall zones, runner targets, invalidation, sizing). Trend comes from LTP.
- **Atlas** = wall building/fading/absorbing → rejection/invalidation.
- **Heatseeker never overrides broken price action.**




⸻

KCU master framework reference

At session start, also read:

~/Desktop/S/setups/TSLA/kcu_framework.md

This file is the master KCU knowledge base extracted from:

* KCU AI Assistant answers
* Our chat-reviewed corrections and gaps
* KCU Indicator official docs
* TSLA-specific Skylit/Heatseeker lessons

Use kcu_framework.md as the KCU rulebook, but this CLAUDE.md remains the TSLA project operating layer.

Source priority

When analyzing trades, use this hierarchy:

1. This CLAUDE.md live TSLA rule file
2. kcu_framework.md
3. TSLA_Playbook.md
4. TSLA_Pattern_Database.md
5. Official KCU Indicator docs
6. Observed trade examples
7. Hypotheses / candidate patterns

If a rule conflicts:

* Follow this CLAUDE.md for TSLA-specific execution.
* Follow kcu_framework.md for general KCU definitions.
* Mark conflicts explicitly as Known from Documentation, Observed Pattern, or Hypothesis.
* Do not silently merge unclear concepts.

⸻

Official KCU Indicator docs to reference

When indicator behavior matters, refer to the official docs:

1. LTP Indicator Setup
    https://docs.google.com/document/d/1eaWl5zXAhxBOtiGpzqoSw-Z7uB05mwiyq6rPCT5GZOA/mobilebasic
2. LTP Indicator Features & Settings
    https://docs.google.com/document/d/1E3RThLMuNxxIj-vXFGW68rOE_rT4l3i-OLhmXsgLhf8/mobilebasic
3. LTP Indicator FAQ
    https://docs.google.com/document/d/1qpZGjmh4JZ4AyH_sk4J_qmGSCAZNbBTyUJte_daU4xw/mobilebasic

Use these docs for:

* LTP Indicator setup assumptions
* supported timeframes
* hourly levels
* PMH/PML
* opening range
* opening price
* VWAP
* SPX Dynamite Zones
* 200 SMA / EMA trend tools
* Auto Fib trend filter
* Pivot structure labels
* Patience Candle visuals
* PC trend filters
* PC approach filters
* PC R:R guides
* NTZ
* Ripster Cloud
* alert behavior
* stop trading reminder

Do not use docs to invent trade-entry logic that is not explicitly taught. Indicator visuals are context and signals, not automatic entries.

⸻

KCU Indicator hard rules

* Supported / intended LTP timeframes: 2m, 5m, 10m, 1h, 1D.
* Intraday LTP trading focus should stay on 2m, 5m, and 10m unless reviewing higher-timeframe levels.
* Use 2m early, 5m after 10:00, and 10m after 11:00 when appropriate.
* Stop Trading reminder appears at 15:00 EST.
* Some Patience Candle visuals, sub-indicators, and alerts do not trigger after 15:00 EST.
* Trading after 15:00 requires extra skepticism and should usually be graded lower unless the setup is clearly clean.

Levels from indicator docs

The LTP Indicator contains:

* Hourly levels
* Dynamite levels
* SPX-specific Dynamite Zones
* SPY overlay of SPX Dynamite Levels
* Psychological levels
* ATH levels
* Premarket high / low
* 15m opening range
* Opening price

Hourly levels:

* Drawn fresh each day around 8:30 EST.
* Intended not to repaint during the day.
* More levels may become visible as price moves away from open.
* For backtesting prior days, use TradingView Replay to see what was visible in real time.

Premarket levels:

* Premarket high/low are drawn from 4:30 EST to 9:30 EST.

Opening range:

* KCU Indicator includes 15m Opening Range levels.

SPX Dynamite Zones:

* SPX treats Dynamite Levels differently.
* On SPX, zones around 50-point Dynamite Levels use roughly +/- 2 points.
* On SPX, zones around 100-point Dynamite Levels use roughly +/- 5 points.
* Somesh may temporarily adjust zone width depending on market conditions.
* For SPX Dynamite Rejection analysis, do not use generic TSLA node logic. Use SPX-specific Dynamite zone context.

⸻

Patience Candle indicator rules

The indicator can show:

* Current patience candles
* All triggered patience candles
* Latest triggered patience candle
* All patience candles

Important:

* A patience candle visual does not automatically equal a valid LTP entry.
* PC arrows only mean the candle satisfied the PC trigger definition.
* Full LTP still requires Level + Trend + Patience Candle.
* Triggered PCs may not consider trend unless PC Trend Filters are applied.
* “All Patience Candles” is mainly for learning/backtesting familiarity, not live trading.
* “Show Only Triggered Patience Candles” is more useful live.

PC trigger definition from docs:

* Bullish PC trigger: high of a contained candle breaks.
* Bearish PC trigger: low of a contained candle breaks.
* The trigger candle is not the PC.
* The PC is the contained candle.
* Entry trigger is the break of that contained candle.

30 Second Rule:

* If enabled, current PC visuals/alerts appear only in the last 30 seconds before candle close.
* This is a warning that a PC may form, not permission to enter.
* If disabled, alerts trigger only after the candle is confirmed as a PC.

⸻

PC filters and how to treat them

PC Trend Filters may filter by:

* Auto Fibonacci Retracement
* Volume
* NTZ
* Premarket Range
* Opening Range
* Previous Day Range
* VWAP
* 21 EMA 5m
* 8 EMA 5m
* EMA Cross

Auto Fib filter:

* Default PC trend filter in newer versions.
* Trend is treated as direction holding the 50% Fib retracement.
* 50% reclaim can be used as trend continuation.
* 59% break can be used as trend reversal.

Volume filter:

* Shows PCs with lower volume than previous candle.

Range filters:

* NTZ / Premarket Range / Opening Range / Previous Day Range filters show PCs outside selected ranges.

VWAP / EMA filters:

* Bullish PCs above the sub-indicator.
* Bearish PCs below the sub-indicator.

Important:

* There is no perfect trend filter.
* Filters reduce noise but can also hide valid entries.
* If filtered PC conflicts with visible price action, explain the conflict.
* Never treat a filtered PC as an automatic trade.

PC Approach Filters:

* Default-on and considered module-aligned.
* They filter out PCs approaching 200 SMAs.
* Concept: do not take trades directly into 200 SMA unless enough room remains.
* PCs about 1.5 R:R away from 200 SMAs may be filtered out.
* In review, always check whether entry is approaching a 200 SMA before PT1.

PC R:R Guides:

* Only visualize reward/risk multiples from the PC.
* They do not account for levels, structure, moving averages, Heatseeker nodes, VWAP, or context.
* Use R:R Guides as a visual check, not a target system.

⸻

KCU source-status rules

Every strategy must be labeled:

* CONFIRMED: enough rules exist to backtest directly.
* PARTIALLY_COVERED: useful rules exist, but management or edge cases are missing.
* CONTRADICTORY: KCU AI/training extraction contains conflicting statements.
* NOT_FORMALLY_DEFINED: concept exists but not as a full setup.
* HYPOTHESIS: inferred from our backtesting, not official.

Do not promote any setup to confirmed unless it has:

* clear entry
* clear stop
* clear PT1/management
* clear invalidation
* repeatable context
* at least 3 similar examples in TSLA logs

⸻

KCU strategy status map

LTP — CONFIRMED

LTP = Levels + Trend + Patience Candle.

Confirmed:

* All three are required.
* Order: Levels first, Trend second, PC third.
* Partial LTP is dangerous.
* Stop comes from the PC.
* Long LTP: entry on break above PC high, stop below PC low.
* Short LTP: entry on break below PC low, stop above PC high.
* PC must be contained.
* Trigger candle is not the PC.
* PC alone does not equal LTP.

Skip LTP if:

* no clean level
* no clean trend
* PC unclear
* PC too large
* levels too close together
* poor R:R
* approaching 200 SMA without room
* price is in middle of range
* same PC/setup already failed

Advanced VWAP — PARTIALLY_COVERED / CONTRADICTORY

Confirmed:

* Long-only in extracted training.
* Price comes from below VWAP.
* Needs PC.
* PC closes above VWAP.
* Entry is next candle after PC closes above VWAP.
* Stop below PC low, or below VWAP if PC is too large.
* Target: intraday levels or open price print.

Contradiction:

* Some extracted notes say it needs trend/trendy stock.
* Some say it works in chop.
* Some say it does not work in strong trend.

Working interpretation for TSLA assistant:

* Do not use in random chop.
* Do not use in runaway trend far extended from VWAP.
* Best candidate context: controlled pullback/reclaim of VWAP after price came from below, with PC and room to target.
* Label market-context confidence as medium/low unless clarified.

King and Queen — MOSTLY_CONFIRMED

Confirmed:

* King = VWAP in extracted training.
* Queens can be 8 EMA, 21 EMA, ORB levels, 200 SMA, opening price, hourly levels, prior support/resistance, or other chart levels.
* King + Queen = confluence zone.
* Levels do not need exact same price; visually close is enough.
* SPY example: roughly 15–20 cents closeness can count.
* Requires some trend.
* Requires PC confirmation.
* Do not enter at confluence alone.
* Without PC, price can blow through confluence.
* Market evolved; PC is now mandatory.

Unclear:

* exact closeness thresholds for TSLA.
* target rules.
* whether used more for continuation, rejection, or both.

TSLA assistant rule:

* Treat King and Queen as confluence only, not standalone entry.
* Require Level + Trend + PC + R:R.

Rejection — PARTIALLY_CONFLICTED BUT USABLE

Confirmed from earlier extraction:

* Rejection = price approaches critical level, touches/gets near it, and sharply moves away.
* Difference from pullback: rejection has conviction and a sharp reaction.
* Difference from reversal: rejection can be a level reaction; reversal changes broader trend.
* Needs critical level.
* Trend and market context matter.
* PC after rejection is preferred/required in extracted notes.
* Entry after PC break, not on rejection candle itself.
* Stop around rejection candle / opposite side depending direction.
* Target next critical level / hourly level.
* Skip if choppy, market against thesis, no clear level, blocking level, poor trend, weak volume.

Conflict:

* Later KCU AI said rejection was not covered in the specific training context.
* Keep as usable but not fully official unless instructor confirms.

Reversal — MOSTLY_CONFIRMED

Confirmed:

* Reversal requires prior trend.
* Reversal is not one rejection candle.
* Takes time to form.
* Requires weakness / volume shift / structure break.
* Requires PC after structure break.
* Bearish reversal after uptrend:
    * structure breaks down
    * PC forms
    * entry direction is break below PC low
    * stop above PC high
* Bullish reversal after downtrend:
    * structure breaks up
    * PC forms
    * entry direction is break above PC high
    * stop below PC low
* Stop is opposite side of PC.
* Targets are less explicitly defined; use next hourly/structure level with manual confidence note.

Still unclear:

* PC close vs next candle break in some examples.
* multiple PCs: which one to use.
* full target system.

TSLA assistant rule:

* Do not call reversal early.
* Classify as REVERSAL_WATCH only after prior trend + weakness + structure break + PC.
* If only sharp level reaction, classify as REJECTION_WATCH, not reversal.

Failed LTP — NOT_FORMALLY_DEFINED

Final decision:

* Failed LTP is not confirmed as a standalone KCU strategy.
* Use as warning/journal tag only.

Confirmed:

* A valid LTP requires Levels + Trend + PC.
* If expected HH/LL fails, structure is suspect.
* Do not keep forcing same LTP.
* Wait for a fresh setup.
* Opposite-direction trade may become reversal-like, but not formally defined.

Not confirmed:

* official entry
* stop
* PT1
* management
* distinction from rejection/reversal
* standalone backtestability

TSLA assistant rule:

* FAILED_LTP_WATCH allowed.
* FAILED_LTP_ENTRY not allowed.
* Alert only: original LTP failed; wait for fresh PC/setup.
* Do not log Failed LTP as confirmed strategy.

ORB — PARTIALLY_COVERED

Confirmed:

* ORB = Opening Range Breakout.
* Indicator uses 15m opening range.
* ORB high/low act as levels.
* Break and continuation suggests trend.
* Break and return into range suggests chop/failed breakout.
* Pure ORB stop/target not fully extracted.

Use ORB as:

* level
* context
* trend/chop diagnostic
* confluence with LTP/PC

ORB Bounce / Reject — COVERED

Confirmed:

* Price breaks out of ORB.
* Then retests ORB.
* Need PC at ORB level.
* Entry uses PC logic.
* Stop is PC-based, though exact detail not fully expanded.
* Target intraday/hourly levels.
* Skip if no PC or no confluence.

Cloud Strategy — MOSTLY_COVERED

Confirmed:

* Afternoon strategy.
* Uses Ripster / Ichimoku Cloud.
* Ripster Cloud visible after 13:00 EST.
* Requires strong morning trend.
* Works after ~1 PM.
* Avoid after 3 PM.
* Price bounces/rejects from cloud.
* Needs PC at cloud.
* Quick scalp, 10–15 minute hold.
* Target HOD or nearby structure.
* Stop implied around bounce/rejection/PC, but exact rule unclear.

TSLA assistant rule:

* Grade Cloud Strategy medium confidence unless stop is clear.
* Use only as afternoon scalp context, not full-size LTP unless all normal gates pass.

Profit Taking — COVERED_WITH_CONFLICT

Confirmed:

* Take profits systematically.
* First profit can be around 50% visual move.
* Then hourly levels.
* Final can be HOD/LOD or next major structure.
* If price action gets ugly/choppy, take profits faster.
* Hourly levels matter.

Conflict:

* KCU AI extraction said stop does not move.
* User’s TSLA execution often uses PT1 → sell half → rest BE.
* Until clarified, log which stop-management model was used.

TSLA assistant default:

* For TSLA 0DTE, continue using user’s existing management:
    * PT1 at valid node/level/R:R
    * sell half
    * move rest to BE only when structure supports
    * runner only with trend + node/PA confirmation

Stock Selection — CONFIRMED

Confirmed:

* Narrow basket is preferred.
* Instructor uses 9 names.
* Avoid random hot tickers.
* Mastering fewer tickers improves behavior/familiarity.

TSLA project implication:

* TSLA-only scope is valid.
* Avoid adding random tickers to this project.
* If comparing broader market, use SPY/QQQ as context only.

No Trade Zones — CONFIRMED

Confirmed no-trade conditions:

* before 9:45 AM lower quality
* lunch 11:30–1 lower quality
* after 3 PM avoid
* no clear trend
* choppy/ugly candles
* price between levels
* no target level
* long below 200 SMA lower quality
* short above 200 SMA lower quality
* price in middle of range
* no clean level
* clustered levels
* weak/no PC
* poor R:R
* same PC/setup already failed

TSLA assistant:

* Default to no-trade over forced trade.
* Log good skips.

⸻

TSLA live assistant classification updates

Use these alert states:

* LTP_UPSIDE_FORMING
* LTP_DOWNSIDE_FORMING
* REJECTION_WATCH
* REVERSAL_WATCH
* FAILED_LTP_WATCH
* ADVANCED_VWAP_WATCH
* KING_AND_QUEEN_CONFLUENCE
* ORB_RETEST_WATCH
* CLOUD_SCALP_WATCH
* CHOP_STAY_OUT
* NO_TRADE
* DISCIPLINE_ALERT

Do not use:

* FAILED_LTP_ENTRY

Failed LTP alert wording

Use:

“Failed LTP watch: original LTP failed to make expected continuation. Do not retry or flip immediately. Wait for a fresh confirmed setup.”

Do not say:
“Take Failed LTP entry.”

Advanced VWAP alert wording

Use:

“Advanced VWAP watch: price came from below VWAP and PC closed above. Entry only on next-candle confirmation. Market context is contradictory in training notes, so size conservatively.”

Reversal alert wording

Use:

“Reversal watch: prior trend + structure break + PC required. Stop should be opposite side of PC. Do not call reversal from one rejection candle.”

Rejection alert wording

Use:

“Rejection watch: level reaction forming. Need PC/confirmation after rejection. Do not enter on the rejection candle alone.”

Cloud alert wording

Use:

“Cloud scalp watch: after 1 PM only, strong morning trend required, PC at cloud required. Quick scalp. Avoid after 3 PM.”

⸻

Backtesting tags to use

Core:

* VALID_LTP
* PARTIAL_LTP
* INVALID_LTP
* CLEAN_TREND
* MESSY_TREND
* CLEAN_LEVEL
* CLUSTERED_LEVELS
* GOOD_PC
* BAD_PC
* PC_TRIGGER
* PC_FAILED
* APPROACHING_200SMA
* BAD_RR
* NO_TRADE

Strategy:

* ADVANCED_VWAP
* KING_AND_QUEEN
* REJECTION
* REVERSAL
* FAILED_LTP_WATCH
* ORB
* ORB_BOUNCE_REJECT
* CLOUD_STRATEGY
* PROFIT_TAKING
* STOCK_SELECTION
* NTZ

Heatseeker:

* GROWING_POSITIVE_NODE_CASCADE
* POSITIVE_NODE_HOLDING
* POSITIVE_NODE_SHRINKING
* NEGATIVE_NODE_FUEL
* KING_NODE_SOFTENING
* KING_NODE_HOLDING
* GATEKEEPER_NODE
* AIR_POCKET
* NODE_BLOCKING_PT1
* NODE_TARGET_VALID
* NODE_TOO_FAR

Discipline:

* FOMO
* FOBI
* CHASE
* FRONT_RUN
* OVER_SIZE
* FAVORITE_TICKER_BIAS
* RETRY_FAILED_PC
* POST_WIN_REENTRY
* REVENGE_TRADE
* WORKED_DESPITE_POOR_SETUP
* HEATSEEKER_MISREAD
* PRICE_ACTION_IGNORED

⸻

Claude startup instruction

At start of each TSLA session:

1. Read this CLAUDE.md.
2. Read kcu_framework.md.
3. Read TSLA_Playbook.md.
4. Read TSLA_Pattern_Database.md.
5. Confirm:
    * TSLA-only
    * backtest mode by default
    * KCU LTP decides go/no-go
    * Heatseeker supports node/target/sizing
    * Failed LTP is warning tag only
    * Advanced VWAP market context remains contradictory
    * no trade over forced trade

One-line confirmation format:

“Ready: TSLA-only backtest mode. KCU LTP = go/no-go, Heatseeker = node/target/sizing, Failed LTP = warning only, unclear rules flagged.”

⸻

## Priority stack
1. Price action 2. KCU structure (real level, not middle) 3. R:R (≥1.5, prefer 2+) 4. Market context (SPY/QQQ tape, time of day) 5. Heatseeker 6. Everything else.

## ⚑ PATIENCE CANDLE — exact definition (Trade 001 correction #3)
- **PC = a candle CONTAINED WITHIN the prior candle's range AND in the direction of the move (inside bar, trend direction).**
- The **break of the PC = the trigger / entry candle. The trigger candle is NOT the PC.** Do not confuse them.
- A bounce/counter-color candle that is contained + breaks down in a downtrend qualifies as a failed-reclaim PC.
- LTP setups: if PC candle is unclear → ASK "Which candle is your PC?" Do not guess.
- Rejection/reversal: identify trigger from visible PA; mark uncertainty if trigger candle unclear.

## ⚑ NODE READ — growing +node = cascade fuel (Trade 001 correction #2)
- A **+GEX node that GROWS while price breaks below it is CASCADE FUEL, not a floor.** Overrides any "first-touch reaction / sloppy seconds / take-profit-at-node" instinct.
- Confirm cascade with: +node growing through the break + **stacked negative nodes beneath** + **king node shrinking** (ceiling softening).
- In a cascade: **target the NEGATIVE nodes below the +node, never cap PT1 at the breaking +node.** Stretch = next untouched +GEX floor below.
- A +node that HOLDS or SHRINKS at the break = real floor → expect bounce (scalp/skip puts).
- King-node rate-of-change must be checked open→entry; shrinking king = ceiling softening, lower conviction for longs / higher for the cascade-down.

## ⚑ Don't misclass velocity entries (Trade 001 correction #1)
- A vertical cascade is velocity context (snapback risk → caps size), but it does NOT make a clean contained PC at a level a "momentum chase." If the PC exists at a level with tight invalidation in trend, it's a valid LTP/failed-reclaim entry. Grade it, don't dismiss it.

## Node distance (0DTE ~1pt PT1)
- 0–2 pts: affects entry/skip. Opposing node here can block PT1 → reduce/skip — UNLESS it's a growing +node cascade (then it's fuel, target beneath it).
- 2–4 pts: valid PT1 / main target. 4–7: PT2/runner only. 7+: ignore for entry (unless King/macro/event).
- Puts: check X-1 to X-2 for blocking support, X-2.5 to X-4 for PT1. Calls: X+1 to X+2 blockers, X+2.5 to X+4 PT1.

## R:R gate (hard)
- Stop ≥ previous candle range. Min R:R **1.5** or skip — regardless of signal quality.
- If R:R fails because PT1 is mis-set AT a node, **retarget first** (check cascade fuel below), then re-test the gate. Don't skip a good entry just because the wrong target was drawn.

## Confirmed adjustments
1. First-90-min is primary focus, but don't auto-reject valid A/A+ after 11:00 — grade lower / require stronger confirmation unless clearly clean.
2. Don't call pullback entries "late" if valid 2m/5m PC in trend near clean invalidation.
3. Always compare intended vs best-available setup; say when LTP is poor and rejection / reverse rug / no-trade is better.
4. Bearish tape (SPY/QQQ −0.5%+): +GEX nodes below price = slowing zones, not reversal; puts valid through them unless king node shows 2+ candles consolidation.

## Heatseeker quick logic
- Yellow/+GEX = stabilizer/sticky S/R/magnet (BUT growing-through-break = cascade fuel). Purple/-GEX = accelerator/fuel.
- King = highest absolute exposure / daily anchor. Gatekeeper = large node between spot & King; fade first-second test, third favors break.
- Air pocket = sparse nodes, fast move, don't fade. Magnitude > color (−80M > +20M). Enter from node/level/PC near invalidation, not empty space.
- Regime: +GEX = chop/mean-revert, fade edges, faster PTs. −GEX = momentum continues, hold runners only with confirmation. VEX/VANNA matters more when VIX > ~20.

## Setup library to compare every time
LTP / trend pullback / rejection / failed reclaim / failed breakdown / front-run / rug pull / reverse rug (slingshot) / reversal / bounce scalp / continuation / no trade.
- Reverse rug = −GEX above +GEX floor; flush holds + reclaim + acceptance = long. No reclaim = bounce scalp only.
- Rug pull = +GEX ceiling over −GEX fuel, little floor; reject ceiling + fall through = short cascade.

## DEFAULT review format (token-efficient)
```
KCU Grade: A+ / A / B+ / B / C / Skip
Heatseeker Grade: Strong Confirmation / Mild Confirmation / Neutral / Warning / Strong Conflict
Sizing: no trade / watch / scalp only / small / half / normal / full
Reason: 3–5 bullets
Management: PT1 / Runner / Invalidation
Playbook Lesson: one sentence
Confidence: 1–10
```
Separate when relevant: Known from Documentation / Observed Pattern / Hypothesis. Never mix.
If Heatseeker read contradicts outcome: write "Heatseeker failed here." Then: what PA warned first / what KCU warned first / should it have been ignored. (Note: if Heatseeker was *misread*, that's a model miss, not a Heatseeker failure — log to Model_Audit.)

## Screenshot intake
Identify first: time, ticker, direction, entry, stop, nearby levels. Then immediately: Take / Skip / Size up / Size down. Reasoning after.
Missing info → "Review confidence limited — missing ___." Still give provisional read + confidence score. Don't hallucinate levels/prices.

## Quick commands
`Q:` → KCU Grade, Heatseeker Grade, Size, Confidence only. `P:` → Playbook lesson only. `DD:`/`Deep Dive`/`Teach Mode` → detailed. `COMPARE:` → two trades, pick one. `SIZE:` → only whether Heatseeker justifies larger/smaller size.

## Logging triggers
On `done`/`next`/`let's move on`/`log this`/`save this`/new trade sequence → finalize + log current trade FIRST, then move on. Log no-trades too (A+ skips, avoided traps, FOMO/FOBI).

Full-log output (LOCAL, actually write): trade_id, folder, Analysis.md, Timeline.md, screenshots_manifest.csv, append TSLA_Trade_Index.csv row + TSLA_R_Equity_Curve.csv row, + changed sections of Playbook / Pattern_Database / Setup_Stats / Best_Examples / Invalidation_Library / Model_Audit. Don't re-output unchanged master content.

## trade_id & folders
trade_id: `TSLA_YYYYMMDD_HHMM_DIRECTION_SETUP_###`
Folder: `~/Desktop/s/setups/TSLA/DATE_TIMESTAMP_TSLA_DIRECTION_SETUP/` → screenshots/ + Analysis.md + Timeline.md + screenshots_manifest.csv.
Screenshot naming: `img_<N>.png` (N = the `[Image #N]` tag from the message it came from).

### ⚑ Saving actual screenshot files (Model Audit 2026-06-19 — don't repeat)
Images shared in chat are cached at `~/.claude/image-cache/<session-id>/<N>.png`, sequential, matching the `[Image #N]` tag. This is reachable via Bash `cp` even when the live screenshot-capture path (`/var/folders/.../TemporaryItems/...`, macOS `screencaptureui` sandbox) returns `Operation not permitted` — that block is real and unrelated to Full Disk Access, but the image-cache copy is unaffected by it. **Before writing "source expired" in any screenshots_manifest.csv, check the image-cache path and copy the real file into `<trade_folder>/screenshots/img_<N>.png`.** Match images to a trade using image-cache file mtimes (`stat -f "%Sm" -t "%H:%M:%S"`), which cluster cleanly by send-batch; spot-check ambiguous cluster boundaries by reading 1-2 images per cluster rather than guessing from conversation memory alone.

**⚑ Timing caveat (Model Audit 2026-06-19, trade 016 — don't repeat):** image-cache filenames are NOT permanently stable within a session — low numbers can get overwritten/reused as new images arrive later in the same conversation (confirmed: same filename, different byte size, at two check points). Do not wait for the "log it" trigger to copy screenshots if a trade is being analyzed live over multiple turns — copy into the trade folder (or a temp holding folder if the trade_id isn't finalized yet) as soon as the images are discussed, not deferred.

## Master files (root)
TSLA_Playbook.md · TSLA_Trade_Index.csv · TSLA_Pattern_Database.md · TSLA_Setup_Stats.md · TSLA_Context_Summary.md · TSLA_Setup_Invalidation_Library.md · TSLA_R_Equity_Curve.csv · TSLA_Best_Examples.md · Weekly_Review.md · TSLA_Schema_Changelog.md · TSLA_Revision_Log.md · TSLA_Model_Audit.md · TSLA_Daily_Prep_Template.md

## Data & process rules
- Every review: review_confidence_score 1–10 + confidence_reason + missing_information + assumptions_made.
- Separate pre-entry facts from hindsight; judge real-time decision quality.
- Schema lock after first 5 trades approved; column changes need approval + changelog entry.
- Duplicate check before new trade_id (date/time/direction/setup/entry).
- Pattern promotion to Playbook needs 3+ similar examples; else "candidate" in Pattern_Database (status: candidate/watchlist/confirmed/deprecated/avoid).
- Full size only on A/A+, R:R ≥2, entry near invalidation, context supports, no blocking node before PT1, positive historical stats, daily risk allows.
- Mistake_tags / edge_tags: use the fixed taxonomy from the addendum; don't invent new tags unless necessary.
- Options execution logged separately from underlying read (strike/expiry/premium/spread/delta/theta/IV).
- New skill installs (incl. find-skills): state name/source/use/permissions, ASK first. Use built-in tools if sufficient.
- Sub-agent roles (now available in Claude Code): image/OCR, trade-analysis, risk/management, pattern-mining, file-logging, summary. Run in parallel where it helps; file-logging agent owns all writes under root.
- Re-read this file + masters every 5–10 trades to prevent drift. If analysis conflicts with playbook, STOP and ask: follow PDF/DOCX rule or updated live rule?

---

## Study skills (installed 2026-06-25)

Source: `RoundTable02/tutor-skills` — installed via `npx skills add RoundTable02/tutor-skills`.
Two skills available: `/tutor-setup` and `/tutor`.

### /tutor-setup
**When to use:** Run once (or after major playbook updates) to convert project knowledge sources into an Obsidian StudyVault under `~/Desktop/s/setups/TSLA/StudyVault/`.

**Sources to point it at (in order of priority):**
1. `TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf` — master KCU PDF
2. `kcu_framework.md` — extracted KCU rules and gaps
3. `TSLA_Playbook.md` — TSLA-specific execution rules
4. `TSLA_Pattern_Database.md` — confirmed + candidate patterns with examples
5. `TSLA_Model_Audit.md` — documented model misses and fixes
6. `TSLA_Setup_Invalidation_Library.md` — invalidation rules

**What it produces:** Concept notes per topic area + practice questions + dashboard tracking proficiency by area.

### /tutor
**When to use:** When Sunny wants to drill KCU/LTP/Heatseeker knowledge, test framework rules, or identify blind spots. Triggers: "quiz me", "test me", "let's study", "drill weak areas".

**Suggested study areas for this project:**
- LTP mechanics (Level, Trend, PC — exact definitions, entry/stop rules)
- Heatseeker node reads (cascade fuel vs floor, King rules, magnitude > color)
- KCU strategy statuses (CONFIRMED vs PARTIALLY_COVERED vs HYPOTHESIS)
- Failed reclaim setups (level identification, PC placement)
- Trade management rules (PT1, runner, fuel-decay exit)
- Model audit lessons (do not re-learn past mistakes)

**Note:** Requires StudyVault to exist (run `/tutor-setup` first if StudyVault is missing).

---

## Trade log so far
- **001 — TSLA_20260618_0936_PUTS_LTP_FAILED_RECLAIM** — A− entry / B target. LTP failed-reclaim short at 391.90/OR-Low; contained-inside-bar PC, break trigger; +390 grew 2.6M→5.1M through break (cascade) over −387.5/−385 fuel, king 400 softening. Win, but PT1 capped at +390 (1.14 R:R) instead of 387.5/385. Candidate pattern: "Growing +Node Cascade (Rug Pull)" 1/3.
- Open model-audit lessons: (1) don't dismiss valid contained-PC as momentum chase in velocity context; (2) growing +node through break = cascade fuel, target beneath; (3) PC = contained+trend-dir, trigger ≠ PC.