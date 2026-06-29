"""Unit tests for the Phase 5B outcome result model."""
from __future__ import annotations

import json

from src.simulator.execution_contract import ExecutionOutcome
from src.simulator.outcome import OutcomeResult


def _result(**overrides) -> OutcomeResult:
    base = dict(
        plan_id="TSLA_2024-01-15_00011",
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
        entry_candle_index=11,
        entry_timestamp=1705334400,
        exit_candle_index=12,
        exit_timestamp=1705334520,
        exit_price=203.0,
        exit_reason="target was touched and stop was not touched in this candle",
        realized_r=1.5,
        outcome_status=ExecutionOutcome.TARGET_BEFORE_STOP,
        counts_as_win=True,
        counts_as_loss=False,
        audit_trail=["simulation started", "terminal decision=TARGET_BEFORE_STOP"],
    )
    base.update(overrides)
    return OutcomeResult(**base)


class TestOutcomeResultValidate:
    def test_valid_result_passes(self):
        assert _result().validate() == []

    def test_ambiguous_requires_none_realized_r(self):
        result = _result(
            exit_price=None,
            realized_r=0.0,
            outcome_status=ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED,
            counts_as_win=False,
            counts_as_loss=False,
        )
        errors = result.validate()
        assert any("AMBIGUOUS_BOTH_TOUCHED" in e for e in errors)

    def test_skipped_requires_none_exit_fields(self):
        result = _result(
            exit_candle_index=12,
            exit_timestamp=1705334520,
            exit_price=203.0,
            realized_r=None,
            outcome_status=ExecutionOutcome.SKIPPED_REJECTED_PLAN,
            counts_as_win=False,
            counts_as_loss=False,
        )
        errors = result.validate()
        assert any("SKIPPED_REJECTED_PLAN" in e for e in errors)

    def test_unresolved_cannot_count_as_win_or_loss(self):
        result = _result(
            exit_price=None,
            realized_r=None,
            outcome_status=ExecutionOutcome.UNRESOLVED_END_OF_REPLAY,
            counts_as_win=True,
            counts_as_loss=False,
        )
        errors = result.validate()
        assert any("UNRESOLVED_END_OF_REPLAY" in e for e in errors)

    def test_audit_trail_must_be_non_empty(self):
        errors = _result(audit_trail=[]).validate()
        assert any("audit_trail" in e for e in errors)


class TestOutcomeResultSerialization:
    def test_to_dict_round_trip(self):
        result = _result()
        rebuilt = OutcomeResult.from_dict(result.to_dict())
        assert rebuilt.to_dict() == result.to_dict()

    def test_to_jsonl_line_is_single_line(self):
        line = _result().to_jsonl_line()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["outcome_status"] == ExecutionOutcome.TARGET_BEFORE_STOP
