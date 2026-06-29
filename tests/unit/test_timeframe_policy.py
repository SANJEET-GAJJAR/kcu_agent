"""Unit tests for timeframe policy and protocol readiness validator.

All tests are offline (no TradingView or collection required).
Tests use tmp_path fixtures to create fake collection artifacts.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from src.collector.timeframe_policy import (
    TimeframeWindow,
    TimeframePolicyConfig,
    TimeframePolicyConfigError,
    load_timeframe_policy,
    collection_path,
    preflight_companion_path,
    validate_protocol_readiness,
    require_protocol_ready,
    ProtocolReadinessError,
    ProtocolReadinessResult,
    CollectionStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    windows: list[dict] | None = None,
    required: dict | None = None,
    allow_derived: bool = False,
) -> TimeframePolicyConfig:
    if windows is None:
        windows = [
            {"start": "09:30", "end": "10:00", "timeframe": "2", "label": "open_range"},
            {"start": "10:00", "end": "16:00", "timeframe": "5", "label": "main_session"},
        ]
    if required is None:
        required = {"full_protocol": ["2", "5"], "smoke_test": ["2"]}
    return TimeframePolicyConfig(
        version="1.0.0",
        policy_name="KCU Standard",
        windows=[TimeframeWindow(**w) for w in windows],
        required_timeframes=required,
        allow_derived_timeframes=allow_derived,
    )


def _write_valid_collection(output_dir: Path, ticker: str, date: str, tf: str) -> Path:
    """Write a minimal valid JSONL + preflight companion."""
    coll = collection_path(ticker, date, tf, output_dir)
    coll.write_text('{"timestamp": 1, "symbol": "TSLA"}\n')
    companion = preflight_companion_path(coll)
    companion.write_text(json.dumps({
        "preflight_passed": True,
        "preflight_warning": False,
        "template_name": "only KCU indicator",
        "indicator_names": ["Stop Loss Widget", "KCU Indicator", "Volume"],
    }))
    return coll


def _write_failed_preflight_collection(output_dir: Path, ticker: str, date: str, tf: str) -> Path:
    """Write a JSONL with a failing preflight companion."""
    coll = collection_path(ticker, date, tf, output_dir)
    coll.write_text('{"timestamp": 1}\n')
    companion = preflight_companion_path(coll)
    companion.write_text(json.dumps({
        "preflight_passed": False,
        "failure_reasons": ["required indicator missing: 'KCU Indicator'"],
    }))
    return coll


# ---------------------------------------------------------------------------
# TimeframePolicyConfig
# ---------------------------------------------------------------------------

class TestTimeframePolicyConfig:
    def test_valid_construction(self):
        cfg = _make_config()
        assert cfg.version == "1.0.0"
        assert len(cfg.windows) == 2
        assert cfg.windows[0].timeframe == "2"
        assert cfg.windows[1].timeframe == "5"

    def test_empty_version_raises(self):
        with pytest.raises(TimeframePolicyConfigError, match="version"):
            TimeframePolicyConfig(
                version="",
                policy_name="x",
                windows=[TimeframeWindow("09:30", "10:00", "2", "open")],
                required_timeframes={"full_protocol": ["2"]},
                allow_derived_timeframes=False,
            )

    def test_empty_windows_raises(self):
        with pytest.raises(TimeframePolicyConfigError, match="windows"):
            TimeframePolicyConfig(
                version="1.0.0",
                policy_name="x",
                windows=[],
                required_timeframes={"full_protocol": ["2"]},
                allow_derived_timeframes=False,
            )

    def test_empty_required_timeframes_raises(self):
        with pytest.raises(TimeframePolicyConfigError, match="required_timeframes"):
            TimeframePolicyConfig(
                version="1.0.0",
                policy_name="x",
                windows=[TimeframeWindow("09:30", "10:00", "2", "open")],
                required_timeframes={},
                allow_derived_timeframes=False,
            )

    def test_allow_derived_true_raises(self):
        with pytest.raises(TimeframePolicyConfigError, match="allow_derived_timeframes"):
            _make_config(allow_derived=True)

    def test_unknown_protocol_level_raises(self):
        with pytest.raises(TimeframePolicyConfigError, match="Unknown protocol level"):
            TimeframePolicyConfig(
                version="1.0.0",
                policy_name="x",
                windows=[TimeframeWindow("09:30", "10:00", "2", "open")],
                required_timeframes={"bogus_level": ["2"]},
                allow_derived_timeframes=False,
            )

    def test_required_for_full_protocol(self):
        cfg = _make_config()
        assert cfg.required_for("full_protocol") == ["2", "5"]

    def test_required_for_smoke_test(self):
        cfg = _make_config()
        assert cfg.required_for("smoke_test") == ["2"]

    def test_required_for_unknown_level_raises(self):
        cfg = _make_config()
        with pytest.raises(TimeframePolicyConfigError, match="Unknown protocol level"):
            cfg.required_for("bogus")


# ---------------------------------------------------------------------------
# Load from YAML
# ---------------------------------------------------------------------------

class TestLoadTimeframePolicy:
    def test_loads_default_config(self):
        cfg = load_timeframe_policy()
        assert cfg.version == "1.0.0"
        assert cfg.policy_name == "KCU Standard"
        assert len(cfg.windows) == 2

    def test_default_windows_are_correct(self):
        cfg = load_timeframe_policy()
        open_range = cfg.windows[0]
        assert open_range.start == "09:30"
        assert open_range.end == "10:00"
        assert open_range.timeframe == "2"
        assert open_range.label == "open_range"

        main_session = cfg.windows[1]
        assert main_session.start == "10:00"
        assert main_session.end == "16:00"
        assert main_session.timeframe == "5"
        assert main_session.label == "main_session"

    def test_full_protocol_requires_2m_and_5m(self):
        cfg = load_timeframe_policy()
        assert "2" in cfg.required_for("full_protocol")
        assert "5" in cfg.required_for("full_protocol")

    def test_smoke_test_requires_2m_only(self):
        cfg = load_timeframe_policy()
        assert cfg.required_for("smoke_test") == ["2"]

    def test_derived_timeframes_not_allowed(self):
        cfg = load_timeframe_policy()
        assert cfg.allow_derived_timeframes is False


# ---------------------------------------------------------------------------
# Collection path helpers
# ---------------------------------------------------------------------------

class TestCollectionPathHelpers:
    def test_collection_path_format(self, tmp_path):
        p = collection_path("TSLA", "2026-06-22", "2", tmp_path)
        assert p.name == "TSLA_2026-06-22_2m.jsonl"
        assert p.parent == tmp_path

    def test_collection_path_5m(self, tmp_path):
        p = collection_path("TSLA", "2026-06-22", "5", tmp_path)
        assert p.name == "TSLA_2026-06-22_5m.jsonl"

    def test_collection_path_ticker_uppercased(self, tmp_path):
        p = collection_path("tsla", "2026-06-22", "2", tmp_path)
        assert p.name == "TSLA_2026-06-22_2m.jsonl"

    def test_preflight_companion_path(self, tmp_path):
        coll = tmp_path / "TSLA_2026-06-22_2m.jsonl"
        comp = preflight_companion_path(coll)
        assert comp.name == "TSLA_2026-06-22_2m_preflight.json"
        assert comp.parent == tmp_path


# ---------------------------------------------------------------------------
# validate_protocol_readiness — full_protocol
# ---------------------------------------------------------------------------

class TestValidateFullProtocol:
    def test_ready_when_both_collections_valid(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is True
        assert len(result.missing) == 0

    def test_not_ready_when_5m_missing(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        # 5m not written
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False
        missing_tfs = [s.timeframe for s in result.missing]
        assert "5" in missing_tfs

    def test_not_ready_when_2m_missing(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False
        missing_tfs = [s.timeframe for s in result.missing]
        assert "2" in missing_tfs

    def test_not_ready_when_both_missing(self, tmp_path):
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False
        assert len(result.missing) == 2

    def test_not_ready_when_5m_preflight_companion_missing(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        # Write 5m JSONL but no companion
        coll = collection_path("TSLA", "2026-06-22", "5", tmp_path)
        coll.write_text('{"timestamp": 1}\n')
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False
        five_status = next(s for s in result.missing if s.timeframe == "5")
        assert "companion" in five_status.missing_reason.lower()

    def test_not_ready_when_5m_preflight_failed(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        _write_failed_preflight_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False
        five_status = next(s for s in result.missing if s.timeframe == "5")
        assert five_status.preflight_passed is False

    def test_not_ready_when_companion_corrupt(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        coll = collection_path("TSLA", "2026-06-22", "5", tmp_path)
        coll.write_text('{"timestamp": 1}\n')
        companion = preflight_companion_path(coll)
        companion.write_text("not valid json {{{{")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is False

    def test_result_fields_populated(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ticker == "TSLA"
        assert result.date == "2026-06-22"
        assert result.protocol_level == "full_protocol"
        assert result.required_timeframes == ["2", "5"]
        assert len(result.statuses) == 2

    def test_summary_shows_all_pass(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        summary = result.summary()
        assert "all" in summary.lower()
        assert "valid" in summary.lower()

    def test_summary_shows_missing(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        summary = result.summary()
        assert "FAILED" in summary
        assert "5m" in summary


# ---------------------------------------------------------------------------
# validate_protocol_readiness — smoke_test
# ---------------------------------------------------------------------------

class TestValidateSmokeTest:
    def test_ready_with_2m_only(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert result.ready is True

    def test_not_ready_when_2m_missing(self, tmp_path):
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert result.ready is False

    def test_5m_present_but_not_checked_in_smoke(self, tmp_path):
        # 5m alone doesn't satisfy smoke_test (which requires 2m)
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert result.ready is False

    def test_smoke_test_does_not_check_5m(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        # 5m absent — smoke_test should still pass
        result = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert result.ready is True
        assert result.required_timeframes == ["2"]

    def test_smoke_test_distinguishes_from_full_protocol(self, tmp_path):
        # 2m only: smoke_test ready, full_protocol not ready
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        smoke = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        full = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert smoke.ready is True
        assert full.ready is False


# ---------------------------------------------------------------------------
# require_protocol_ready
# ---------------------------------------------------------------------------

class TestRequireProtocolReady:
    def test_does_not_raise_when_ready(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "5")
        result = require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert result.ready is True

    def test_raises_when_5m_missing(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        with pytest.raises(ProtocolReadinessError) as exc_info:
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert "5m" in str(exc_info.value)
        assert "FAILED" in str(exc_info.value)

    def test_raises_when_both_missing(self, tmp_path):
        with pytest.raises(ProtocolReadinessError):
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")

    def test_smoke_test_raises_when_2m_missing(self, tmp_path):
        with pytest.raises(ProtocolReadinessError):
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "smoke_test")

    def test_smoke_test_does_not_raise_with_2m(self, tmp_path):
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        result = require_protocol_ready("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert result.ready is True

    def test_error_message_names_ticker_and_date(self, tmp_path):
        with pytest.raises(ProtocolReadinessError) as exc_info:
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")
        msg = str(exc_info.value)
        assert "TSLA" in msg
        assert "2026-06-22" in msg

    def test_error_message_names_protocol_level(self, tmp_path):
        with pytest.raises(ProtocolReadinessError) as exc_info:
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert "full_protocol" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Protocol policy gap: 2m-only is not valid for full KCU protocol
# ---------------------------------------------------------------------------

class TestProtocolPolicyGap:
    def test_existing_2m_collection_is_valid_for_smoke_test(self, tmp_path):
        """2m-only collection: acceptable for smoke test, NOT for full protocol."""
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        smoke = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "smoke_test")
        assert smoke.ready is True

    def test_existing_2m_collection_is_invalid_for_full_protocol(self, tmp_path):
        """Confirms the gap: 2m-only blocks full_protocol pipeline."""
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        full = validate_protocol_readiness("TSLA", "2026-06-22", tmp_path, "full_protocol")
        assert full.ready is False
        assert any(s.timeframe == "5" for s in full.missing)

    def test_missing_5m_prevents_full_dry_run(self, tmp_path):
        """Missing 5m collection must block the full KCU dry run."""
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        with pytest.raises(ProtocolReadinessError) as exc_info:
            require_protocol_ready("TSLA", "2026-06-22", tmp_path, "full_protocol")
        msg = str(exc_info.value)
        assert "5m" in msg

    def test_full_protocol_requires_independent_5m(self, tmp_path):
        """5m must be an independent collection — not derived from 2m."""
        policy = load_timeframe_policy()
        assert policy.allow_derived_timeframes is False
        # Only 2m present: full_protocol fails
        _write_valid_collection(tmp_path, "TSLA", "2026-06-22", "2")
        result = validate_protocol_readiness(
            "TSLA", "2026-06-22", tmp_path, "full_protocol", policy=policy
        )
        assert result.ready is False


# ---------------------------------------------------------------------------
# No trading logic in source
# ---------------------------------------------------------------------------

class TestNoTradingLogicInPolicy:
    _TRADING_TERMS = [
        "entry", "stop_loss", "take_profit", "position_size",
        "risk_reward", "target_price",
    ]

    def test_no_trading_terms(self):
        path = Path("src/collector/timeframe_policy.py")
        source = path.read_text().lower()
        for term in self._TRADING_TERMS:
            assert term not in source, (
                f"Trading term {term!r} found in timeframe_policy.py"
            )
