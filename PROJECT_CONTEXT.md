# PROJECT_CONTEXT.md
# KCU Backtesting Engine — Living Project State
# Last Updated: 2026-06-29

---

## Current Milestone
Milestone 1 — Replay-Safe Backtesting Engine

## Current Phase
**Phase 7 — Human Review** ✅ COMPLETE

## Phase Status

| Phase | Name                               | Status        |
|-------|------------------------------------|---------------|
| 0     | Repository Bootstrap               | ✅ Complete    |
| 1A    | TradingView MCP Wrapper + Replay   | ✅ Complete    |
| 1B    | Day Collector (full day → JSONL)   | ✅ Complete    |
| 2     | Offline Replay Engine              | ✅ Complete    |
| 3     | Feature Extraction                 | ✅ Complete    |
| 4A    | Setup Candidate Detection          | ✅ Complete    |
| 4B    | Setup Confirmation / Grading       | ✅ Complete    |
| 4C    | Level Context Engine + Preflight   | ✅ Complete    |
| 5A    | Trade Plan Construction            | ✅ Complete    |
| 5A.1  | Execution Contract + Plan Integrity Hardening | ✅ Complete |
| 5B    | Outcome Simulation                 | ✅ Complete    |
| 5C    | Day Runner + Outcome Persistence   | ✅ Complete    |
| 6A    | Statistics Core                    | ✅ Complete    |
| 6A.1  | Statistics Integrity Guard         | ✅ Complete    |
| 6B    | Reporting Layer                    | ✅ Complete    |
| 6C    | Aggregate Statistics               | ✅ Complete    |
| 6D    | Report Output Path Standardization | ✅ Complete    |
| 7A    | Human Review Schema + Review Queue | ✅ Complete    |
| 7B    | Human Review Decisions             | ✅ Complete    |
| 7C    | Review Revision / Override Workflow | ✅ Complete   |
| 7D    | Human-Friendly Review Export       | ✅ Complete    |
| X     | Model Router CLI                   | ✅ Complete    |
| 6     | Statistics            | ✅ Complete    |
| 7     | Human Review          | ✅ Complete    |
| 8     | Memory                | ⬜ Not Started |
| 9     | Live Assistant        | ⬜ Not Started |

Phase 6 completion note:
- 6A Statistics Core
- 6A.1 Statistics Integrity Guard
- 6B Reporting Layer
- 6C Aggregate Statistics
- 6D Report Output Path Standardization

Phase 7 completion note:
- 7A Human Review Schema + Review Queue
- 7B Human Review Decisions
- 7C Review Revision / Override Workflow
- 7D Human-Friendly Review Export

---

## Repository Layout

```
backtesting/
├── CLAUDE.md                    # Project constitution (read-only for Claude)
├── PROJECT_CONTEXT.md           # This file — living project state
├── IMPLEMENTATION_PLAN.md       # Phase-by-phase implementation details
├── config/
│   ├── models.yaml              # Model routing config (model-agnostic)
│   ├── chart_template.yaml      # Chart preflight requirements (Phase 4C)
│   └── timeframe_policy.yaml    # Timeframe policy: 2m (09:30-10:00), 5m (10:00-16:00)
├── knowledge/                   # Static human-controlled references
├── src/
│   ├── collector/               # Phase 1: TradingView MCP collector
│   │   ├── chart_preflight.py   # Chart environment validation (Phase 4C)
│   │   └── timeframe_policy.py  # Timeframe policy validator (pre-pipeline gate)
│   ├── engine/                  # Phase 2: Replay engine (replay_engine, backtest_replay, policy_replay)
│   ├── features/                # Phase 3: Feature extraction
│   │   └── level_context.py     # Level Context Engine (Phase 4C)
│   ├── detectors/               # Phase 4: Setup detection (LTP/rejection/reversal/bounce)
│   ├── simulator/               # Phase 5: Trade simulation
│   ├── review/                  # Phase 7: Human review schema + queue
│   ├── statistics/              # Phase 6: Daily statistics
│   └── utils/                   # Shared utilities
├── outputs/
│   ├── candles/                 # Collected candle data (JSONL)
│   ├── features/                # Extracted features per day
│   ├── trades/                  # Simulated trade records
│   └── reports/                 # Daily statistics reports
├── tests/
│   ├── unit/                    # Unit tests per module
│   ├── integration/             # Cross-module integration tests
│   └── fixtures/                # Test candle data
└── memory/                      # Future phase
```

---

## Key Decisions

- **Ticker**: TSLA only (Milestone 1)
- **Target**: 90 trading days
- **Scenario watch layer**: watch-only confluence logging is allowed before setup confirmation, but it never creates trade plans or auto-promotes rules
- **Simulation**: 1.5R fixed-target trades
- **Execution ambiguity**: both stop and target in the same candle = `AMBIGUOUS_BOTH_TOUCHED`
- **Persistence isolation**: every day-run writes into a `run_id`-scoped output directory
- **Statistics policy**: ambiguous and unresolved outcomes never count as wins or losses
- **Statistics integrity**: aggregation runs only on complete and cross-file consistent day-run artifacts
- **Reporting policy**: integrity failures produce invalid reports with no performance claims
- **Aggregate policy**: only integrity-passing day runs contribute to multi-day performance metrics
- **Canonical report paths**: daily and aggregate reports can be mirrored into `outputs/reports/...` with stable metadata for downstream phases
- **Timeframe policy**: KCU protocol uses 2m (09:30–10:00 ET) and 5m (10:00–16:00 ET); both must be independently collected — derivation from another timeframe is never permitted
- **Protocol levels**: `smoke_test` requires 2m only; `full_protocol` requires both 2m and 5m with valid preflight companions
- **Pipeline gate**: `require_protocol_ready()` must pass before the full KCU pipeline runs; missing 5m blocks the full dry run
- **Human review queue**: Phase 7A builds deterministic pending-review entries from valid day artifacts only
- **Human review decisions**: Phase 7B persists append-only human labels against existing queued review items only
- **Human review revisions**: Phase 7C persists append-only corrections without mutating original human decisions
- **Human review export**: Phase 7D builds deterministic human-readable dashboard and item exports from queue, decisions, revisions, and daily report artifacts
- **Scenario watch layer**: deterministic pre-confirmation `scenario_events.jsonl` can be generated from detector labels, level context, and indicator confluence without changing confirmation or simulation semantics
- **Lookahead**: Strictly prohibited — replay mode only
- **AI for math**: Never — all calculations are Python
- **Architecture**: Frozen at v1

## Model Routing

| Task | Model |
|---|---|
| Architecture, debugging, conflict resolution | `architecture_model` (Claude) |
| Implementation, boilerplate, docs | `implementation_model` (ollama-cloud / glm-5.2:cloud) |
| Code review, optimization, testing | `review_model` (Codex) |
| All calculations, replay, statistics | `deterministic_engine` (Python) |

**Phase X (Model Router CLI) is complete.** `config/models.yaml` is now an active dispatch config.

To route an implementation task:
```bash
python scripts/route_task.py --task <name> --prompt "..."
python scripts/route_task.py --task <name> --prompt-file prompts/task.txt
python scripts/route_task.py --task <name> --dry-run   # inspect config without dispatching
```

The router reads `implementation_model` from `config/models.yaml`, dispatches via subprocess,
logs every attempt to `outputs/model_router/router_log.jsonl`, tries fallbacks in order on
failure, and raises `ModelUnavailableError` if all models fail. It will never fall back to Claude.

Claude Code must not continue implementation-heavy work unless the user explicitly approves
each session. Use the router to hand off to the configured implementation model.

## Scope Exclusions (Milestone 1)
- Heatseeker, Atlas, Kronos, Obsidian
- Memory / self-learning
- Live assistant
- Multi-ticker support

---

## Dependencies
- Python 3.14 (venv at `venv/`)
- pyyaml (config loading)
- pytest + pytest-asyncio (validation)
- mcp==1.28.1 (MCP client SDK for TradingView bridge)
- Node.js (tradingview-mcp server — started separately, requires TradingView Desktop + CDP port 9222)

## Validation State
- Phase 0 bootstrap validation: ✅ PASSED (26/26)
- Phase 1A unit tests: ✅ PASSED (49/49)
- Phase 1B unit tests: ✅ PASSED (110/110 cumulative)
- Phase 2 unit tests: ✅ PASSED (172/172 cumulative)
- Phase 2 risk remediation: ✅ PASSED (206/206 cumulative)
- Phase 2 policy replay (PolicyReplay + 51 new tests): ✅ PASSED (1213/1213 cumulative)
- Milestone 1 dry run — TSLA 2026-06-22: ✅ PIPELINE COMPLETE (all 11 steps, 0 candidates — data quality issue in collected candles; O=H=L=C throughout)
- Phase 1B OHLCV bug investigation: ✅ RESOLVED + RECOLLECTED (root cause: after replay_step(), lastIndex() is forming bar O=H=L=C=open_tick; fix: getOhlcv() two-stage fallback — Stage 1 dataWindowView, Stage 2 bars.valueAt(lastIndex()-1); TSLA 2026-06-22 recollected: 2m=350 bars/10 pre-market degenerate, 5m=145 bars/0 degenerate; all quality gates pass; pipeline ran fully)
- KCU indicator quality gate: ✅ FIXED (pre-market bars before 9:30 AM ET excluded from KCU presence check — indicator not loaded until market open; false positive eliminated)
- plan_id collision: ✅ FIXED (plan_id now uses candidate_candle_index + setup_type instead of evaluated_at_candle_index; multiple setups at same candle no longer collide)
- Milestone 1 dry run: ✅ COMPLETE (TSLA 2026-06-22, real OHLCV: 242 merged candles, 176 candidates, 6 confirmed setups, 2 valid trade plans, 2 outcomes: 1 GAP_BEYOND_STOP + 1 STOP_BEFORE_TARGET, 2 losses, -2.0 R, 2 review queue entries, full reports written)
- Workspace protection: layout_get_current DOM detection returns null on Desktop; fallback uses layout_list single-match → layout "KCU" detected, verified=True; config/workspace.yaml updated to backtest_workspace_name: "KCU"
- Phase 1B indicator collection: ✅ EXTENDED (raw_indicators field added to CandleRecord; KCU/optional study quality gate; indicator_quality report; 13 new tests; 1226/1226 cumulative)
- Workspace protection: ✅ COMPLETE (WorkspacePreflight blocks live workspace; config/workspace.yaml; layout_get_current MCP tool; 22 new tests; 1248/1248 cumulative)
- Phase 3 unit tests: ✅ PASSED (344/344 cumulative)
- Phase 4A unit tests: ✅ PASSED (430/430 cumulative)
- Phase 4A KCU audit: ✅ PASSED (481/481 cumulative)
- Phase 4B confirmation engine: ✅ PASSED (596/596 cumulative)
- Phase 4C chart preflight: ✅ PASSED (57 new tests)
- Phase 4C level context engine: ✅ PASSED (126 new tests)
- Preflight hardening patch: ✅ PASSED (37 new tests)
- Phase 5A trade plan construction: ✅ PASSED (138 new tests)
- Phase 5A semantics audit: ✅ PASSED (11 additional tests, 939 total)
- Phase 5A.1 execution contract + plan integrity hardening: ✅ PASSED (21 new tests; focused regression slice 237/237)
- Phase 5B outcome simulation: ✅ PASSED (19 new tests; focused regression slice 136/136)
- Phase 5C day runner + persistence: ✅ PASSED (5 new tests; focused regression slice 155/155)
- Phase 6A statistics core: ✅ PASSED (5 new tests; focused regression slice 28/28)
- Phase 6A.1 statistics integrity guard: ✅ PASSED (7 additional tests; focused regression slice 35/35)
- Phase 6B reporting layer: ✅ PASSED (4 new tests; focused regression slice 16/16)
- Phase 6C aggregate statistics: ✅ PASSED (5 new tests; focused regression slice 21/21)
- Phase 6D report output path standardization: ✅ PASSED (2 additional path tests; focused regression slice 23/23)
- Phase 7A human review schema + queue: ✅ PASSED (6 new tests; focused regression slice 17/17)
- Phase 7B human review decisions: ✅ PASSED (5 new tests; focused regression slice 11/11)
- Phase 7C review revision / override workflow: ✅ PASSED (5 new tests; focused regression slice 16/16)
- Phase 7D human-friendly review export: ✅ PASSED (5 new tests; focused regression slice 21/21)
- Scenario watch layer: ✅ IMPLEMENTED (watch-only confluence logging; focused unit coverage for bounce, rejection, continuation, raw-indicator fallback, and JSONL persistence)
- Scenario watch checkpoint — TSLA 2026-06-22: regular-session scenarios = 68; premarket scenarios = 0; 10:00–11:00 scenarios = 3; 10:55 bounce/reclaim is now represented as BOUNCE_WATCH; 10:35 LTP puts is still missing; 09:50 rejection zone remains represented nearby; 09:54 dual-watch exists and remains unresolved pending more examples; recommended next step: run the same pipeline on 2–3 additional TSLA days with known good setups before making more detector/scenario changes
- Phase X model router: ✅ PASSED (64 new tests, 1003 total)
- Full-suite cumulative baseline before Phase 5A.1 additions: ✅ PASSED (1003/1003)
- Preflight hardening (MCP protocol fix + KCU substring match): ✅ PASSED (58 preflight + 37 enforcement = 95 tests)
- Timeframe policy validator: ✅ PASSED (45 new tests; focused regression slice 140/140)
