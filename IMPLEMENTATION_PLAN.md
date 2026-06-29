# IMPLEMENTATION_PLAN.md
# KCU Backtesting Engine — Phase Implementation Plans
# Last Updated: 2026-06-29

---

## Scenario Watch Layer ✅ COMPLETE

**Goal**: Create deterministic watch-only scenario candidates from confluence zones before any setup confirms.

**Deliverables**:
- [x] `src/detectors/scenario_event.py` — `ScenarioEvent`, `ScenarioType`, `ScenarioConfidence`
- [x] `src/detectors/scenario_watch.py` — `ScenarioWatchEngine`, config, JSONL writer/loader
- [x] `tests/unit/test_scenario_watch.py` — bounce, rejection, continuation, raw-indicator fallback, persistence coverage

**Output**:
- `scenario_events.jsonl`

**Contract**:
- Watch-only records only: no entries, stops, targets, sizing, or outcomes
- `scenario_type` in `BOUNCE_WATCH | REJECTION_WATCH | LTP_CONTINUATION_WATCH`
- `confidence` is always `WATCH`
- `source_status` is always `HYPOTHESIS`
- Scenario generation may use existing detector labels, level context, and KCU indicator values for confluence
- Human review is still required before any rule becomes confirmed

**Acceptance Criteria**:
- 10:55 bounce area can be represented as `BOUNCE_WATCH` when PDH/200MA confluence is present
- 09:50 rejection area can be represented as `REJECTION_WATCH` when ORH/PDH/200MA confluence is present
- Scenarios are persisted even when no trade is taken

---

## Timeframe Policy — Pre-Pipeline Gate ✅ COMPLETE

**Goal**: Enforce the KCU protocol's multi-timeframe requirement before any full pipeline run.
The KCU protocol uses different chart timeframes for different parts of the session:
- 09:30–10:00 ET: 2m candles (open range)
- 10:00–16:00 ET: 5m candles (main session)

Both must be independently collected. The pipeline must block until both exist.

**Deliverables**:
- [x] `config/timeframe_policy.yaml` — session windows, required timeframes per protocol level
- [x] `src/collector/timeframe_policy.py` — config loader, collection path helpers, readiness validator
- [x] `tests/unit/test_timeframe_policy.py` — 45 tests

**API**:
```python
policy = load_timeframe_policy()                          # load config/timeframe_policy.yaml
result = validate_protocol_readiness(                     # check, don't raise
    "TSLA", "2026-06-22", Path("outputs/candles"),
    protocol_level="full_protocol",                       # or "smoke_test"
)
result.ready          # True if all required collections present and valid
result.missing        # list[CollectionStatus] — what's missing and why
result.summary()      # human-readable status string

require_protocol_ready(...)  # same as above but raises ProtocolReadinessError if not ready
```

**Protocol levels**:
| Level | Required timeframes | Use case |
|---|---|---|
| `smoke_test` | 2m only | Verify collection and preflight infrastructure |
| `full_protocol` | 2m + 5m | Real KCU backtest run |

**Design decisions**:
- `allow_derived_timeframes: false` is enforced — 5m must always be independently collected
- Validation checks both file existence AND preflight_passed=True in the companion file
- Corrupt or missing preflight companions fail the same as preflight_passed=False
- Protocol levels are extensible via config without code changes

**Acceptance Criteria**: 45/45 tests pass ✅ (focused regression slice 140/140)

**Blocked by**: TSLA 2026-06-22 5m collection still required for full_protocol readiness.
**Current state**: 2m collected (smoke_test: READY). 5m not yet collected (full_protocol: NOT READY).

---

## Phase 0 — Repository Bootstrap ✅ COMPLETE

**Goal**: Create the directory structure, config, and validation scaffold so all future phases have a clean foundation.

**Deliverables**:
- [x] Directory tree: knowledge/, config/, src/*, outputs/*, tests/*, memory/
- [x] config/models.yaml (model-agnostic routing)
- [x] PROJECT_CONTEXT.md
- [x] IMPLEMENTATION_PLAN.md
- [x] src/utils/config_loader.py
- [x] tests/test_phase0_bootstrap.py
- [x] .gitignore

**Acceptance Criteria**:
- Directory structure exists
- config/models.yaml loads without error
- ConfigLoader reads and validates models.yaml
- Bootstrap test passes

---

## Phase 1A — TradingView MCP Wrapper & Replay Controller ✅ COMPLETE

**Goal**: Build the infrastructure layer between Python and TradingView MCP. Pure I/O. No business logic.

**Deliverables**:
- [x] src/collector/tv_client.py — async MCP client wrapper with retry logic
- [x] src/collector/replay_controller.py — load ticker, load day, set timeframe, advance candle, read candle, read indicators, export snapshot
- [x] src/collector/candle_schema.py — CandleSnapshot dataclass with strict validation and JSON export
- [x] tests/unit/test_candle_schema.py (17 tests)
- [x] tests/unit/test_tv_client.py (8 tests)
- [x] tests/unit/test_replay_controller.py (24 tests — includes no-trading-logic assertion)

**Acceptance Criteria**: All 49 unit tests pass ✅

**Key design choices**:
- `TradingViewClient` is a pure async MCP client — manages one stdio session to tradingview-mcp
- `ReplayController` enforces a required setup sequence: load_ticker → set_timeframe → load_trading_day
- `CandleSnapshot` validates at construction — corrupt data never propagates
- All tool calls retry up to 3× with exponential backoff
- `_require_replay_active()` guard prevents any data read without an active replay session

---

## Phase 1B — Day Collector ✅ COMPLETE

**Goal**: Collect one complete trading day (premarket through market close) to validated append-only JSONL.

**Deliverables**:
- [x] src/collector/candle_record.py — `CandleRecord` = `CandleSnapshot` + indicators + `raw_indicators` + meta; compact JSONL line serialisation
- [x] src/collector/jsonl_store.py — append-only JSONL writer; duplicate detection by timestamp; resume via seen-timestamp set; `validate_jsonl()` checker
- [x] src/collector/session_clock.py — DST-aware ET session boundary timestamps via `zoneinfo`; `expected_candle_count()`
- [x] src/collector/day_collector.py — `collect_day(ticker, date, timeframe, ...)` async API; stuck detection; session-end boundary; resume-safe; idempotent; no-trading-logic assertion; OHLC quality gate; indicator quality gate; workspace preflight integration
- [x] src/collector/workspace_preflight.py — `WorkspacePreflight` blocks live workspace; `WorkspaceConfig`; `load_workspace_config()`; fail-closed on unknown workspace; override flag; metadata written to CollectionResult
- [x] config/workspace.yaml — live/backtest workspace names; `allow_unknown_workspace_for_collection: false` by default
- [x] tradingview-mcp: `layout_get_current` tool (DOM + TradingViewApi detection paths)
- [x] tests/unit/test_candle_record.py (6 tests)
- [x] tests/unit/test_jsonl_store.py (17 tests)
- [x] tests/unit/test_session_clock.py (12 tests)
- [x] tests/unit/test_day_collector.py (36 tests — OHLC quality, indicator quality, raw_indicators, no-trading-logic)
- [x] tests/unit/test_workspace_preflight.py (22 tests — live blocked, unknown blocked by default, override, backtest passes, runs-first, metadata)

**Acceptance Criteria**: All Phase 1B tests pass ✅ (1248/1248 cumulative)

**JSONL record schema** (one compact line per candle):
```json
{
  "timestamp": 1705270800,
  "open": 195.0, "high": 196.5, "low": 194.0, "close": 196.0, "volume": 100000.0,
  "symbol": "TSLA", "timeframe": "2", "replay_date": "2024-01-15",
  "indicators": {"RSI": 55.2, "VWAP": 195.5},
  "meta": {"candle_index": 0, "collected_at": "2024-01-15T14:30:00+00:00"}
}
```

**Output path**: `outputs/candles/{TICKER}_{DATE}_{TF}m.jsonl`

**Key design choices**:
- End-of-day detection: session_end_ts (4 PM ET by default) OR 3 consecutive stuck steps
- Resume: on open, load all seen timestamps from existing JSONL; skip writing known timestamps while still advancing replay
- Idempotent: second run on a complete file writes 0 records (fast-path via `_is_already_complete`)
- Timeframe aliases: "2m" and "2" both accepted; normalised on entry
- DST handled by `zoneinfo.ZoneInfo("America/New_York")` — no manual offset math

---

## Phase 2 — Offline Replay Engine ✅ COMPLETE

**Goal**: Deterministic offline replay of a collected JSONL trading day. Zero network dependency.

**Deliverables**:
- [x] src/engine/replay_engine.py — `ReplayEngine`, `ReplayState`, exceptions (`EndOfReplay`, `BeginningOfReplay`, `TimestampNotFound`)
- [x] tests/unit/test_replay_engine.py (62 tests)

**API**:
```python
replay = ReplayEngine("outputs/candles/TICKER_2024-01-15_2m.jsonl")
replay.current()            # CandleRecord at cursor
replay.next()               # advance one candle → new CandleRecord (raises EndOfReplay at end)
replay.previous()           # move back one candle (raises BeginningOfReplay at start)
replay.goto("2024-01-15T09:30:00-05:00")  # jump to ISO or int timestamp
replay.finished()           # True when at last candle
replay.at_beginning()       # True when at first candle
replay.reset()              # return to candle 0
replay.state()              # frozen ReplayState snapshot
```

**Post-delivery fixes (risk remediation)**:
- [x] Iterator bug fixed: `__next__` now yields the last candle correctly (was raising `StopIteration` too early)
- [x] `src/engine/backtest_replay.py` — `BacktestReplay` wrapper with `LookaheadGuardError` guard
- [x] `tests/unit/test_backtest_replay.py` — 34 tests covering permitted ops, blocked ops, iteration, lookahead invariant
- [x] Iterator tests updated to assert all candles including last are yielded

**Timeframe policy replay (added this session)**:
- [x] `src/engine/policy_replay.py` — `PolicyReplay`, `PolicyReplayError`, `_policy_boundary_ts`, `_load_records`
- [x] `tests/unit/test_policy_replay.py` — 51 tests

**PolicyReplay API**:
```python
# Production: validates protocol readiness (both 2m+5m preflight required)
replay = PolicyReplay.from_protocol(ticker, date, Path("outputs/candles"))

# Explicit paths with preflight validation
replay = PolicyReplay.from_validated_paths(path_2m, path_5m, date)

# Tests only (no preflight enforcement)
replay = PolicyReplay.from_paths(path_2m, path_5m, date)

replay.current()     # CandleRecord at cursor (2m or 5m depending on position)
replay.next()        # advance one candle (raises EndOfReplay at end)
replay.goto(ts)      # forward-only jump (raises LookaheadGuardError for backward)
replay.finished()    # True at last candle
replay.at_beginning()
replay.state()       # frozen ReplayState snapshot

# Blocked (raise LookaheadGuardError):
replay.previous()    # blocked
replay.reset()       # blocked
replay.peek_next()   # blocked
```

**Key design choices**:
- Candles loaded once into an immutable `tuple[CandleRecord, ...]` sorted by timestamp
- Duplicates removed on load (keep first occurrence)
- Cursor is the only mutable state
- `goto()` uses `bisect.bisect_left` on a parallel timestamps tuple — O(log n)
- `goto()` accepts Unix int, ISO 8601 string (with or without TZ offset), or numeric string
- `peek_next()` exists for engine-internal use only; documented as lookahead-unsafe for callers
- `__iter__`/`__next__` supported for convenience; iterator does not reset
- No hardcoded tickers; no trading logic (verified by source-scan tests)
- `PolicyReplay` boundary derived from policy config (`_policy_boundary_ts` finds earliest 5m window start)
- Pre-boundary candles (timestamps < 10:00 ET) come from 2m file; post-boundary from 5m file
- Boundary candle at exactly 10:00 ET comes from 5m file (5m condition is `>=`)
- `from_protocol()` enforces `require_protocol_ready("full_protocol")` before loading
- `from_validated_paths()` enforces `require_valid_collection()` on both files
- `from_paths()` is for unit tests only — no preflight check

---

## Phase 3 — Feature Extraction ✅ COMPLETE

**Goal**: Build a deterministic feature extraction engine that converts replay candles into structured features. Produces features only — no trading logic, no setup identification.

**Deliverables**:
- [x] `src/features/feature_config.py` — `FeatureConfig` dataclass; configurable windows; validates invariants at construction
- [x] `src/features/feature_record.py` — `FeatureRecord` dataclass; all features flat; nullable for first-candle history; `validate()`, `to_jsonl_line()`, `from_dict()`
- [x] `src/features/rolling_window.py` — `RollingWindow(max_size)`; append-only deque; `snapshot()` returns immutable tuple (oldest→newest); caller pushes AFTER extraction
- [x] `src/features/candle_features.py` — pure stateless functions: body, wicks, range, body_pct, ATR, gap_from_prev, distance_from_prev_close, is_higher_high, is_lower_low, is_inside_bar, is_outside_bar, consecutive_hh/ll/lh/hl, relative_volume, classify_session, time_since_open_minutes, distance_from_session_open
- [x] `src/features/extractor.py` — `FeatureExtractor(replay: BacktestReplay)`; imports `BacktestReplay` only, never `ReplayEngine`; `.run()` returns all `FeatureRecord`s; `.step()` for manual stepping
- [x] `tests/unit/test_feature_extractor.py` — 112 tests covering all features, no-lookahead invariant, no-biz-logic assertion, determinism, no-hardcoded-tickers

**Acceptance Criteria**: All 112 Phase 3 tests pass ✅ (344 total)

**Key design choices**:
- `FeatureExtractor` enforces `BacktestReplay` at construction via `isinstance` check — raw `ReplayEngine` raises `TypeError`
- Window contains only past candles; `push()` happens after extraction
- ATR = simple average of `candle_range` (not True Range) — deterministic, no close-to-close dependency
- Consecutive streak counts walk backward through window until streak breaks
- Session boundaries computed once at extractor init from `replay_date`; DST-safe via `session_clock.session_end_timestamp()`
- `distance_from_session_open` latches the first regular-session candle's close; None for all premarket candles
- Indicator dict is shallow-copied at extraction time — caller's dict cannot mutate stored record

---

## Phase 4A — Setup Candidate Detection Engine (with KCU Audit) ✅ COMPLETE

**Goal**: Build a deterministic plugin-style engine that consumes FeatureRecords and emits structured CandidateEvents — one per detector per candle. KCU-aligned: all events are WATCH-only; no grading, no confirmation, no entry/stop/target.

**Deliverables**:
- [x] `src/detectors/kcu_candidate_contract.py` — `KCUSourceStatus`; `WATCH_CANDIDATE_TYPES`; `FORBIDDEN_CANDIDATE_TYPES`; `ReasonCode` vocabulary; per-setup-type component constants (`LTP_ALL_COMPONENTS`, `LTP_DETECTABLE_COMPONENTS`, etc.); unified `CONTRACT` dict
- [x] `src/detectors/candidate_event.py` — `CandidateEvent` with KCU fields: `source_status`, `reason_codes`, `supporting_components`, `required_missing_components`, `invalidating_components`, `no_trade_risk`; `validate()` enforces WATCH-only status
- [x] `src/detectors/base_detector.py` — `DetectorConfig`; `BaseDetector` ABC with `_make_event()` requiring all KCU fields
- [x] `src/detectors/ltp_detector.py` — emits `LTP_WATCH` (HYPOTHESIS); detects patience_candle; exposes level_context + trend_context as required_missing
- [x] `src/detectors/rejection_detector.py` — emits `REJECTION_WATCH` (HYPOTHESIS); detects rejection_wick; level_context + directional_context missing
- [x] `src/detectors/reversal_detector.py` — emits `REVERSAL_WATCH` (PARTIALLY_COVERED); detects trend_exhaustion + change_of_character; only level_context missing
- [x] `src/detectors/bounce_detector.py` — emits `BOUNCE_WATCH` (PARTIALLY_COVERED); detects support_reaction + directional_wick; only level_context missing
- [x] `src/detectors/failed_ltp_watch_detector.py` — emits `FAILED_LTP_WATCH` (PARTIALLY_COVERED); detects prior_compression + expansion_failure; no missing components
- [x] `src/detectors/chop_detector.py` — emits `CHOP` (PARTIALLY_COVERED); detects contained_range; no missing components
- [x] `src/detectors/detector_engine.py` — `DetectorEngine`; `process()` / `run()` / `register()` / `reset()` / `default()` factory
- [x] `tests/unit/test_detectors.py` — 137 tests: per-detector KCU field validation, KCU audit class, plugin API, no-lookahead, no-biz-logic source scan

**Acceptance Criteria**: All 137 Phase 4A tests pass ✅ (481 cumulative)

**KCU Audit Requirements Met**:
- No detector emits `LTP`, `REJECTION`, `REVERSAL`, `BOUNCE` (unqualified — old labels)
- No detector emits `VALID_LTP` or any confirmed-status label
- No event has `source_status = CONFIRMED`
- Every event has non-empty `no_trade_risk`
- `LTP_WATCH` always carries `level_context` and `trend_context` in `required_missing_components`
- `supporting_components` only contains names from the contract's `detectable` set
- All reason_codes are stable uppercase identifiers

**Key design choices**:
- `detect(features, window)` is pure: same inputs → same output; no mutable state in detectors
- `window` contains only past FeatureRecords; `DetectorEngine` pushes current AFTER all detectors run
- Plugin architecture: `DetectorEngine.register(detector)` adds any `BaseDetector` subclass; no existing code modified
- `kcu_candidate_contract.py` is the single source of truth for component names — detectors import from it
- `HYPOTHESIS` vs `PARTIALLY_COVERED` distinguishes how many required components remain unverified
- `CONFIRMED` is structurally impossible to emit from Phase 4A — validation rejects it

---

## Phase 4B — Setup Confirmation Engine ✅ COMPLETE

**Goal**: Evaluate WATCH candidates from Phase 4A against KCU component confirmation
requirements. Emit CONFIRMED_SETUP or REJECTED_SETUP for each candidate.
No entry, stop, target, sizing, or trade management.

**Deliverables**:
- [x] `src/detectors/confirmation_event.py` — `ConfirmationEvent` dataclass; `ConfirmationOutcome`; `ConfirmationReasonCode`; `validate()`, `to_jsonl_line()`, `from_dict()`
- [x] `src/detectors/confirmation_config.py` — `ConfirmationConfig` (grading thresholds, decisive-break threshold, max wait)
- [x] `src/detectors/setup_evaluators.py` — per-type stateless evaluators: `LTPEvaluator`, `RejectionEvaluator`, `ReversalEvaluator`, `BounceEvaluator`, `FailedLTPWatchEvaluator`, `ChopEvaluator`
- [x] `src/detectors/confirmation_engine.py` — `ConfirmationEngine`; `step()` / `run()` / `flush()` / `reset()`; immediate + deferred evaluation tiers
- [x] `tests/unit/test_confirmation.py` — 115 tests: per-evaluator checks, engine orchestration, KCU Phase 4B audit, no-trade-management source scan, no-lookahead verification

**Acceptance Criteria**: All 115 Phase 4B tests pass ✅ (596 cumulative)

**Evaluation taxonomy**:

| Watch Type | Evaluation | Outcome | Reason |
|---|---|---|---|
| LTP_WATCH | Immediate | REJECTED | level_context + trend_context unverified |
| REJECTION_WATCH | Immediate | REJECTED | level_context + directional_context unverified |
| REVERSAL_WATCH | Immediate | REJECTED | level_context unverified |
| BOUNCE_WATCH | Immediate | REJECTED | level_context unverified |
| FAILED_LTP_WATCH | Deferred (N+1) | CONFIRMED or REJECTED | decisive_directional_break check |
| CHOP | Deferred (N+1) | CONFIRMED or REJECTED | directional_range_expansion check |

**Grading** (CONFIRMED_SETUP only):
- FAILED_LTP_WATCH: Grade A (body < 10%), B (body < 20%), C (body < detector max)
- CHOP: Grade A (inside_bar trigger), B (structural trigger only)

**Key design choices**:
- `ConfirmationEngine.step()` processes deferred pending BEFORE new candidates — no lookahead
- Deferred candidates are evaluated exactly once at N+1; `flush()` force-rejects any remaining
- `ConfirmationEvent.grade=None` is enforced for REJECTED_SETUP by `validate()`
- `source_status=CONFIRMED` is only set on CONFIRMED_SETUP — never on rejected events
- No trade fields exist anywhere in the confirmation schema (verified by dataclass field scan in tests)
- Level database requirement is explicitly documented in each rejection reason for future phases

---

## Task 1 — TradingView Preflight & Collection Validation ✅ COMPLETE

**Goal**: Ensure every candle collection is provably gathered under the correct TradingView chart environment.

**Deliverables**:
- [x] `config/chart_template.yaml` — required template name, required indicators, KCU indicator key variants, versioning
- [x] `src/collector/chart_preflight.py` — `ChartPreflightConfig`, `ChartPreflight`, `PreflightResult`, `PreflightFailedError`, `load_preflight_config()`, `validate_collection()`, `write_preflight_companion()`
- [x] `src/collector/day_collector.py` — `preflight_config: ChartPreflightConfig | None` parameter; `preflight_metadata` on `CollectionResult`; preflight runs before collection loop; companion file written on success
- [x] `tests/unit/test_chart_preflight.py` — 57 tests

**Acceptance Criteria**: All 57 tests pass ✅

**Required indicators**:
- Stop Loss Widget (exact name, case-insensitive)
- KCU Indicator (any name from `kcu_indicator_keys`, e.g. "KCU", "KCU Backtesting")
- Volume (exact name, case-insensitive)

**Preflight result metadata** (written to `{stem}_preflight.json`):
```json
{
  "template_name": "only KCU indicator",
  "indicator_names": ["Stop Loss Widget", "KCU Indicator", "Volume"],
  "required_indicators_present": true,
  "kcu_indicator_version": "1.2.3",
  "preflight_passed": true,
  "collection_version": "1.0.0",
  "collector_version": "1.0.0"
}
```

**Key design choices**:
- `ChartPreflight.validate(dict)` is pure — testable with no TradingView connection
- `ChartPreflight.run(client, output_dir)` is async — calls `chart_get_state` MCP tool
- Failure writes `preflight_failed.json` to output_dir and raises `PreflightFailedError`
- `validate_collection(path)` reads companion JSON — `False` if file missing or `preflight_passed != True`
- `preflight_config=None` (default) skips preflight — backward compatible with existing collection tests
- KCU indicator key matching uses `kcu_indicator_keys` as aliases: chart named "KCU" counts as "KCU Indicator"
- Unknown KCU version is allowed when the indicator is present (captured as "unknown")

---

## Phase 4C — Level Context Engine ✅ COMPLETE

**Goal**: Build a deterministic Level Context Engine that extracts price levels from FeatureRecords. Provides the foundation required before LTP, Rejection, Reversal, and Bounce setups can ever be confirmed.

**Deliverables**:
- [x] `src/features/level_context.py` — `LevelSource`, `NamedLevel`, `LevelConfig`, `LevelRecord`, `LevelExtractor`; pure analysis helpers: `_find_nearest`, `_distance_to_nearest`, `_compute_touch`, `_compute_reclaim`, `_compute_reject`, `_compute_hold`, `_compute_in_middle`, `_compute_clustered`
- [x] `tests/unit/test_level_context.py` — 126 tests

**Acceptance Criteria**: All 126 tests pass ✅

**Supported level types**:

| Level | Source Strategy | Source Tag |
|---|---|---|
| PMH (Pre-Market High) | max(high) of premarket candles in window + current if premarket | derived |
| PML (Pre-Market Low) | min(low) of premarket candles | derived |
| PDH (Prior Day High) | `indicators` dict key PDH / "Prior Day High" | indicator |
| PDL (Prior Day Low) | `indicators` dict | indicator |
| PDC (Prior Day Close) | `indicators` dict key PDC / "Prior Day Close" | indicator |
| ORH (Opening Range High) | max(high) of first `opening_range_minutes` regular candles; only after OR complete | derived |
| ORL (Opening Range Low) | min(low) of OR candles | derived |
| VWAP | `indicators` dict key VWAP / Vwap / vwap | indicator |
| OPEN (Opening Price) | first regular session candle's close, latched | derived |
| H{HH}_HIGH/LOW | max/min of all past candles in that ET hour | derived |

**Per-candle outputs**:
- `nearest_level_above` / `nearest_level_below` — `NamedLevel | None` with name, value, source
- `distance_to_nearest_level` — absolute price distance; None if no known levels
- `level_touch` — bool | None: close within `touch_threshold_pct` of any level
- `level_reclaim` — bool | None: close crossed above a level from below since prior candle
- `level_reject` — bool | None: close crossed below a level from above since prior candle
- `level_hold` — bool | None: close and last N closes all on same side of a level
- `in_middle_of_range` — bool | None: NOT within `touch_threshold_pct` of any level
- `clustered_levels` — list[str]: level names clustered within `cluster_threshold_pct` of price
- `distance_to_open` — float | None: close - opening_price
- `distance_to_vwap` — float | None: close - vwap

**Key design choices**:
- `LevelExtractor.step()` maintains its own `deque[FeatureRecord]` window (separate from the candle-level RollingWindow — avoids type coupling)
- Opening price latched BEFORE `_compute()` so the first regular candle knows its own opening price
- PMH/PML include the CURRENT candle when it is premarket (its close is known); ORH/ORL use PAST candles only
- PDH/PDL/PDC: UNKNOWN when not in indicators (no cross-day data available in single-day replay)
- `LevelSource.UNKNOWN` is never False or 0 — all unknown values are explicitly `None` with `source="unknown"`
- Binary analysis functions return `None` (not False) when input is insufficient
- LevelConfig thresholds: `touch_threshold_pct=0.15`, `cluster_threshold_pct=0.25`, `hold_lookback=3`
- No lookahead verified: ORH/ORL never use current candle; hourly levels only include fully elapsed hours

---

## Preflight Hardening Patch ✅ COMPLETE

**Goal**: Make chart preflight mandatory for all production collection/backtest runs.

**Deliverables**:
- [x] `config/models.yaml` — added `fallback_order`, `signin_command`, `scope`, `trade_simulation` routing, `preflight_mandatory` and `implementation_by_worker_model` policies
- [x] `src/collector/day_collector.py` — `ProductionPreflightRequiredError`; `dry_run: bool = False` parameter; raises before TV connection when `dry_run=False` and `preflight_config=None`
- [x] `src/collector/chart_preflight.py` — `StaleCollectionError`; `require_valid_collection(path)` raises StaleCollectionError for missing/failed/corrupt companions
- [x] `src/engine/backtest_replay.py` — `BacktestReplay.from_validated_path()` enforces preflight before creating replay
- [x] `tests/unit/test_preflight_enforcement.py` — 37 tests

**Enforcement rules**:
1. `collect_day()` raises `ProductionPreflightRequiredError` when `dry_run=False` (default) and `preflight_config=None`
2. Unit tests must pass `dry_run=True` to bypass enforcement
3. `require_valid_collection(path)` raises `StaleCollectionError` for any collection missing a valid companion
4. `BacktestReplay.from_validated_path(path)` calls `require_valid_collection()` before constructing replay
5. `BacktestReplay.from_path()` (unvalidated) remains available for tests using synthetic JSONL fixtures

**Acceptance Criteria**: All 37 tests pass ✅

---

## Phase 5A — Trade Plan Construction ✅ COMPLETE

**Goal**: Build deterministic trade plans from CONFIRMED_SETUP events. Hypothetical plans only.

**Deliverables**:
- [x] `src/simulator/trade_plan.py` — `TradePlan`, `TradePlanDirection`, `PlanStatus`
- [x] `src/simulator/plan_builder.py` — `PlanConfig`, `PlanBuilder`, `_infer_direction`
- [x] `tests/unit/test_trade_plan.py` — 66 tests
- [x] `tests/unit/test_plan_builder.py` — 72 tests

**Acceptance Criteria**: All 138 tests pass ✅

**Supported setup types** (Phase 5A):
- `CHOP` — breakout direction from body commitment → valid plan
- `FAILED_LTP` — plan produced when eval candle has directional body; rejected when doji

**Plan construction rules**:
1. Input: `ConfirmationEvent` (Phase 4B) + `FeatureRecord` at `evaluated_at_candle_index`
2. Gate 1: `outcome == CONFIRMED_SETUP` — else `REJECTED_NOT_CONFIRMED`
3. Gate 2: `setup_type in supported_setup_types` — else `REJECTED_UNSUPPORTED_TYPE`
4. Direction: `close > open` → long; `close < open` → short; `close == open` → `REJECTED_MISSING_FIELDS`
5. Entry trigger: `close` of eval candle
6. Stop: `low` (long) or `high` (short) of eval candle
7. Risk: `abs(entry - stop)`; if `< min_risk_dollars` → `REJECTED_MISSING_FIELDS`
8. Target: `entry ± target_r * risk` (default target_r = 1.5)
9. R:R: `reward_risk = target_r`; if `< min_rr_threshold` → `REJECTED_RR_BELOW_MINIMUM`

**Semantics audit** (applied in same session):
- CHOP is hardcoded as `NON_TRADABLE_SETUP_TYPES` — confirmed CHOP always → `REJECTED_NOT_TRADABLE`
- `tradable_setup_types` defaults to empty frozenset — nothing tradable until explicitly configured
- Confirmed setup ≠ tradable setup: two separate gates (Gate 3 for structural non-tradable, Gate 4 for config)
- FAILED_LTP disabled by default; enable via `PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"}))`
- Added `PlanStatus.REJECTED_NOT_TRADABLE`
- Added `KNOWN_SETUP_TYPES` and `NON_TRADABLE_SETUP_TYPES` module constants

**Not implemented** (future phases):
- Win/loss outcome simulation
- Performance statistics
- Live trading, AI reasoning, screenshots

---

## Phase 5A.1 — Execution Contract & Plan Integrity Hardening ✅ COMPLETE

**Goal**: Lock the canonical execution semantics for Phase 5B and harden
`PlanBuilder` so it cannot construct a plan from misaligned confirmation/event data.

**Deliverables**:
- [x] `src/simulator/execution_contract.py` — `ExecutionOutcome`, `ExecutionDecision`, `CandleExecutionView`, scan-start helpers, gap/intrabar/unresolved/skip resolution helpers
- [x] `src/simulator/plan_builder.py` — deterministic alignment gate between `ConfirmationEvent` and `FeatureRecord`
- [x] `tests/unit/test_execution_contract.py` — 13 tests
- [x] `tests/unit/test_plan_builder.py` — 5 new alignment-hardening tests
- [x] `tests/unit/test_trade_plan.py` — 3 new plan-status tests

**Acceptance Criteria**: Focused regression slice passes ✅ (237/237)

**Alignment rules**:
1. `eval_features.candle_index` must equal `event.evaluated_at_candle_index`
2. `eval_features.symbol` must equal `event.symbol`
3. `eval_features.timeframe` must equal `event.timeframe`
4. `eval_features.replay_date` must equal `event.replay_date`
5. Any mismatch produces `PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH`

**Canonical execution rules**:
1. Outcome scanning starts at `plan.candle_index + 1`
2. The eval candle can never determine outcome
3. Rejected plans are skipped deterministically
4. Gap resolution is checked before intrabar touches
5. If both stop and target are touched in the same candle:
   `ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED`, `realized_r=None`
6. End-of-replay/session without resolution is
   `ExecutionOutcome.UNRESOLVED_END_OF_REPLAY`

**Not implemented**:
- Full outcome simulator
- Trade JSONL outputs
- Statistics

---

## Phase 5B — Outcome Simulation ✅ COMPLETE

**Goal**: Simulate whether a TradePlan hit its target or stop using replay candles.

**Deliverables**:
- [x] `src/simulator/outcome.py` — `OutcomeResult` dataclass with validation and JSONL serialization
- [x] `src/simulator/simulator.py` — `OutcomeSimulator`, `simulate_trade_plan()`, forward-only replay orchestration
- [x] `tests/unit/test_outcome.py` — 7 tests
- [x] `tests/unit/test_simulator.py` — 11 tests

**Acceptance Criteria**: Focused regression slice passes ✅ (136/136)

**Execution guarantees**:
1. Only valid plans are simulated
2. Outcome scanning starts at `plan.candle_index + 1`
3. Same-candle evaluation is structurally impossible
4. All terminal decisions are delegated to `execution_contract.py`
5. Gap, target, stop, ambiguity, and unresolved rules are deterministic

**Not implemented**:
- Day-level trade-plan persistence
- Day summary outputs
- Statistics

**Entry Condition**: Phase 5A.1 complete

---

## Phase 5C — Day Runner + Outcome Persistence ✅ COMPLETE

**Goal**: Wire confirmation events / trade plans into deterministic day-level outputs.

**Deliverables**:
- [x] `src/simulator/day_runner.py` — `DayRunner`, `DayRunArtifacts`, `DayRunResult`, path-based wrappers
- [x] `tests/unit/test_day_runner.py` — 5 tests

**Acceptance Criteria**: Focused regression slice passes ✅ (155/155)

**Persistence outputs**:
- `trade_plans.jsonl` — valid plans only
- `rejected_trade_plans.jsonl` — rejected plans only
- `trade_outcomes.jsonl` — outcomes for valid plans only
- `day_runner_summary.json` — simple deterministic counts + plan ids

**Runner rules**:
1. Production inputs use `BacktestReplay.from_validated_path()`
2. Rejected plans are persisted but never simulated
3. Outputs are isolated under a `run_id`-scoped directory
4. Repeated runs with the same inputs and `run_id` are deterministic
5. No statistics beyond simple counts in the summary

**Entry Condition**: Phase 5B complete

---

## Phase 6A — Statistics Core ✅ COMPLETE

**Goal**: Compute deterministic basic statistics from persisted day-run artifacts.

**Deliverables**:
- [x] `src/statistics/core.py` — artifact readers, validators, deterministic aggregators, JSON writers
- [x] `src/statistics/__init__.py` — public exports
- [x] `tests/unit/test_statistics_core.py` — 5 tests

**Acceptance Criteria**: Focused regression slice passes ✅ (28/28)

**Inputs**:
- `trade_outcomes.jsonl`
- `trade_plans.jsonl`
- `rejected_trade_plans.jsonl`
- `day_runner_summary.json`

**Outputs**:
- `stats_summary.json`
- `stats_by_setup.json`
- `stats_by_direction.json`
- `stats_by_grade.json`

**Deterministic stats included**:
1. total plans
2. valid plans
3. rejected plans
4. simulated trades
5. wins
6. losses
7. ambiguous
8. unresolved
9. win rate
10. average realized R
11. total realized R
12. best trade
13. worst trade

**Rules**:
1. Ambiguous and unresolved outcomes do not count as wins or losses
2. Empty inputs are safe and produce zero/`None` summaries
3. Malformed or invalid persisted records fail clearly via `StatisticsInputError`
4. Aggregation is deterministic and file output is stable across repeated runs

---

## Phase 6A.1 — Statistics Integrity Guard ✅ COMPLETE

**Goal**: Refuse statistics aggregation unless persisted day-run artifacts are
complete and internally consistent.

**Deliverables**:
- [x] `src/statistics/core.py` — cross-file integrity validation and `stats_integrity_report.json`
- [x] `tests/unit/test_statistics_core.py` — 7 additional integrity-guard tests

**Acceptance Criteria**: Focused regression slice passes ✅ (35/35)

**Integrity checks**:
1. Every valid trade plan must have exactly one outcome
2. Every outcome must reference an existing valid trade plan
3. Rejected trade plans must not have outcomes
4. Summary counts must match file contents
5. Duplicate plan ids fail
6. Duplicate outcome plan references fail
7. Empty runs are allowed only when summary counts are zero

**Output**:
- `stats_integrity_report.json`

**Rule**:
- Statistics aggregation aborts with `StatisticsInputError` if integrity fails

---

## Phase 6B — Reporting Layer ✅ COMPLETE

**Goal**: Generate deterministic human-readable reports from existing statistics artifacts.

**Deliverables**:
- [x] `src/statistics/reporting.py` — report artifact loader, formatter, and writers
- [x] `src/statistics/__init__.py` — public reporting exports
- [x] `tests/unit/test_statistics_reporting.py` — 4 report-layer tests

**Acceptance Criteria**: Focused regression slice passes ✅ (16/16)

**Inputs**:
- `stats_summary.json`
- `stats_by_setup.json`
- `stats_by_direction.json`
- `stats_by_grade.json`
- `stats_integrity_report.json`

**Outputs**:
- `daily_report.md`
- `daily_report.json`

**Rules**:
1. Reporting performs no new calculations beyond formatting existing statistics artifacts
2. Integrity failures produce an explicit invalid report and omit performance claims
3. Empty valid days render cleanly in markdown and JSON
4. Repeated report generation is deterministic

---

## Phase 6C — Aggregate Statistics ✅ COMPLETE

**Goal**: Aggregate multiple completed day-run statistics into deterministic multi-day reports.

**Deliverables**:
- [x] `src/statistics/aggregate.py` — aggregate loaders, deterministic combiners, JSON/markdown writers
- [x] `src/statistics/__init__.py` — public aggregate exports
- [x] `tests/unit/test_statistics_aggregate.py` — 5 aggregate-layer tests

**Acceptance Criteria**: Focused regression slice passes ✅ (21/21)

**Inputs**:
- Multiple day run folders containing:
  - `stats_summary.json`
  - `stats_by_setup.json`
  - `stats_by_direction.json`
  - `stats_by_grade.json`
  - `stats_integrity_report.json`

**Outputs**:
- `aggregate_stats_summary.json`
- `aggregate_by_setup.json`
- `aggregate_by_direction.json`
- `aggregate_by_grade.json`
- `aggregate_report.md`
- `aggregate_report.json`

**Rules**:
1. Only days with passing integrity contribute to aggregate performance metrics
2. Invalid or duplicate-run days are skipped and listed deterministically
3. Empty aggregates are safe and produce zero/`None` summaries
4. Aggregate ordering is stable across repeated runs

---

## Phase 6D — Report Output Path Standardization ✅ COMPLETE

**Goal**: Standardize daily and aggregate report output paths for downstream consumption.

**Deliverables**:
- [x] `src/statistics/reporting.py` — canonical daily report path support and metadata
- [x] `src/statistics/aggregate.py` — canonical aggregate report path support and metadata
- [x] `tests/unit/test_statistics_reporting.py` — canonical daily path coverage
- [x] `tests/unit/test_statistics_aggregate.py` — canonical aggregate path coverage

**Acceptance Criteria**: Focused regression slice passes ✅ (23/23)

**Canonical output structure**:
- `outputs/reports/daily/{ticker}/{date}/{run_id}/`
- `outputs/reports/aggregate/{ticker}/{range_or_batch_id}/`

**Metadata added to report JSON**:
- `ticker`
- `date`
- `run_id`
- `report_type`
- `generated_at`
- `source_stats_path`
- `integrity_status`

**Rules**:
1. Existing in-run report artifacts remain in place for compatibility
2. Canonical path writing is additive and does not recalculate statistics
3. Daily and aggregate report JSON payloads expose stable downstream metadata

---

## Phase 6 — Statistics ✅ COMPLETE

**Goal**: Compute daily and aggregate statistics from simulated trades.

**Completed subphases**:
- 6A Statistics Core
- 6A.1 Statistics Integrity Guard
- 6B Reporting Layer
- 6C Aggregate Statistics
- 6D Report Output Path Standardization

**Completion note**:
- Phase 6 umbrella gate is now satisfied for Phase 7 entry.

**Entry Condition**: Phase 5 complete

---

## Phase 7A — Human Review Schema + Review Queue ✅ COMPLETE

**Goal**: Define deterministic human review queue records and build a queue from valid day artifacts.

**Deliverables**:
- [x] `src/review/schema.py` — review queue entry contract and validation
- [x] `src/review/queue.py` — deterministic daily review queue builder and persistence
- [x] `src/review/__init__.py` — public review exports
- [x] `tests/unit/test_review_schema.py` — schema tests
- [x] `tests/unit/test_review_queue.py` — queue tests

**Acceptance Criteria**: Focused regression slice passes ✅ (17/17)

**Outputs**:
- `human_review_queue.jsonl`
- `human_review_summary.json`

**Rules**:
1. Queue entries are built only from valid day artifacts with a valid daily report
2. Rejected trade plans are excluded from the review queue
3. Queue persistence is deterministic and can mirror to the canonical daily report path
4. No human decisions, memory, or interpretation are implemented in Phase 7A

---

## Phase 7B — Human Review Decisions ✅ COMPLETE

**Goal**: Persist deterministic human review decisions for queued review items.

**Deliverables**:
- [x] `src/review/decision.py` — human review decision contract, append-only writer, JSONL loader
- [x] `src/review/__init__.py` — public decision exports
- [x] `tests/unit/test_review_decision.py` — decision tests

**Acceptance Criteria**: Focused regression slice passes ✅ (11/11)

**Outputs**:
- `human_review_decisions.jsonl`

**Rules**:
1. Every decision references an existing queued review item and persisted plan/outcome ids
2. Decision labels are restricted to the approved deterministic set
3. Duplicate decisions for the same review item fail deterministically
4. No memory, learning, playbook updates, statistics changes, or outcome changes are implemented in Phase 7B

---

## Phase 7C — Review Revision / Override Workflow ✅ COMPLETE

**Goal**: Persist deterministic human review corrections without mutating original decisions.

**Deliverables**:
- [x] `src/review/revision.py` — revision contract, append-only writer, deterministic effective-decision resolver
- [x] `src/review/__init__.py` — public revision exports
- [x] `tests/unit/test_review_revision.py` — revision tests

**Acceptance Criteria**: Focused regression slice passes ✅ (16/16)

**Outputs**:
- `human_review_revisions.jsonl`

**Rules**:
1. Original decisions remain immutable in `human_review_decisions.jsonl`
2. Valid revisions append to a separate revision artifact only
3. Effective latest decision resolves deterministically from the original decision plus ordered revisions
4. Multiple revisions are allowed only when they advance deterministically by previous-effective reference and/or monotonic revision sequence
5. No memory, playbook updates, statistics changes, or outcome changes are implemented in Phase 7C

---

## Phase 7D — Human-Friendly Review Export ✅ COMPLETE

**Goal**: Generate deterministic human-readable review exports from queue, decision, revision, and daily report artifacts.

**Deliverables**:
- [x] `src/review/export.py` — deterministic review dashboard and review item exporters
- [x] `src/review/__init__.py` — public export exports
- [x] `tests/unit/test_review_export.py` — export tests

**Acceptance Criteria**: Focused regression slice passes ✅ (21/21)

**Outputs**:
- `review_dashboard.md`
- `review_dashboard.json`
- `review_items.md`
- `review_items.json`

**Rules**:
1. Export works with queue-only artifacts and safely handles missing optional decisions/revisions
2. Effective latest review label is resolved from the original decision plus revisions when present
3. Review items remain deterministically ordered by queue timestamp/order
4. No memory, learning, Obsidian, playbook updates, statistics changes, or outcome changes are implemented in Phase 7D

---

## Phase 7 — Human Review ✅ COMPLETE

**Goal**: Present evidence for human review and approval.

**Completed subphases**:
- 7A Human Review Schema + Review Queue
- 7B Human Review Decisions
- 7C Review Revision / Override Workflow
- 7D Human-Friendly Review Export

**Completion note**:
- Phase 7 umbrella gate is satisfied for Milestone 1 human-review artifact generation.

**Entry Condition**: Phase 6 complete

---

## Phases 8–9 — Future

Not in Milestone 1 scope.

---

## Phase X — Model Router CLI ✅ COMPLETE

**Goal**: Build the missing bridge between `config/models.yaml` and actual work dispatch,
so repetitive implementation tasks are routed to the configured implementation model
automatically rather than falling back to Claude Code by default.

**Deliverables**:
- `src/router/config_loader.py` — loads and validates `config/models.yaml`
- `src/router/dispatch.py` — dispatches prompt to configured model via subprocess; handles fallbacks
- `src/router/router_log.py` — appends `{timestamp, task, model, provider, fallback_used, ...}` to `outputs/model_router/router_log.jsonl`
- `src/router/model_router.py` — public `ModelRouter` façade
- `scripts/route_task.py` — CLI entry point
- `tests/unit/test_model_router.py` — 64 tests, all mocked (no real Ollama called)

**Behaviour**:
- Reads `implementation_model` from `config/models.yaml`
- Dispatches to configured model via subprocess (prompt via stdin, output via stdout)
- Tries `fallback_order` entries on failure; skips any Claude entry silently
- Logs every attempt to `outputs/model_router/router_log.jsonl`
- Raises `ModelUnavailableError` if all models fail — never silently falls back to Claude
- Raises `ClaudeRouteAttemptError` if `implementation_model.provider` is `claude` or `anthropic`

**CLI usage**:
```bash
python scripts/route_task.py --task implement_outcome_simulation --prompt "..."
python scripts/route_task.py --task boilerplate --prompt-file prompts/task.txt
python scripts/route_task.py --task x --dry-run   # inspect config, no dispatch
```

Exit codes: 0 = success, 1 = unavailable, 2 = config error, 3 = Claude route blocked

**Entry Condition**: ✅ Complete — 1003/1003 tests pass
