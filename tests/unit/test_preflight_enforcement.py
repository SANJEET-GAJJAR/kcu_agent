"""Tests for preflight enforcement hardening.

Covers:
  - Production collection requires preflight_config
  - dry_run=True explicitly bypasses requirement (unit test mode)
  - Stale collections (missing or failed preflight) cannot be replayed
  - Model routing config separates implementation_model from architecture_model
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.collector.chart_preflight import (
    StaleCollectionError,
    require_valid_collection,
    write_preflight_companion,
    PreflightResult,
)
from src.collector.day_collector import (
    ProductionPreflightRequiredError,
    collect_day,
)
from src.engine.backtest_replay import BacktestReplay, LookaheadGuardError

_MODELS_CONFIG = Path(__file__).parents[2] / "config" / "models.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, timestamps: list[int]) -> None:
    """Write a minimal valid JSONL fixture."""
    import json
    lines = []
    for i, ts in enumerate(timestamps):
        lines.append(json.dumps({
            "timestamp": ts, "open": 100.0, "high": 101.0,
            "low": 99.0, "close": 100.5, "volume": 1000,
            "symbol": "TSLA", "timeframe": "2",
            "replay_date": "2024-01-15", "candle_index": i,
            "session": "regular", "indicators": {},
        }))
    path.write_text("\n".join(lines) + "\n")


def _preflight_result(passed: bool = True) -> PreflightResult:
    return PreflightResult(
        template_name="only KCU indicator",
        indicator_names=["Stop Loss Widget", "KCU Indicator", "Volume"],
        required_indicators_present=passed,
        kcu_indicator_version="1.2.3" if passed else "unknown",
        preflight_passed=passed,
        collection_version="1.0.0",
        collector_version="1.0.0",
        failure_reasons=[] if passed else ["required indicator missing: 'Stop Loss Widget'"],
    )


# ---------------------------------------------------------------------------
# Production Collection Enforcement
# ---------------------------------------------------------------------------

class TestProductionCollectionRequiresPreflight:
    """collect_day() without preflight_config must fail in production mode."""

    @pytest.mark.asyncio
    async def test_fails_without_preflight_config(self, tmp_path):
        """Calling collect_day() without preflight_config raises immediately."""
        with pytest.raises(ProductionPreflightRequiredError):
            await collect_day(
                "TSLA", "2024-01-15", "2",
                output_dir=tmp_path,
                # preflight_config omitted → None by default
            )

    @pytest.mark.asyncio
    async def test_dry_run_false_is_default(self, tmp_path):
        """dry_run defaults to False, so omitting preflight_config raises."""
        with pytest.raises(ProductionPreflightRequiredError):
            await collect_day("TSLA", "2024-01-15", "2", output_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_error_message_mentions_dry_run(self, tmp_path):
        """Error message tells developer how to bypass in tests."""
        with pytest.raises(ProductionPreflightRequiredError, match="dry_run=True"):
            await collect_day("TSLA", "2024-01-15", "2", output_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_error_message_mentions_load_preflight_config(self, tmp_path):
        """Error message mentions load_preflight_config() for production use."""
        with pytest.raises(ProductionPreflightRequiredError, match="load_preflight_config"):
            await collect_day("TSLA", "2024-01-15", "2", output_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_error_raises_before_tv_connection(self, tmp_path):
        """ProductionPreflightRequiredError is raised synchronously before any
        async TV connection, so it is safe to test without mocking TV."""
        raised = False
        try:
            await collect_day("TSLA", "2024-01-15", "2", output_dir=tmp_path)
        except ProductionPreflightRequiredError:
            raised = True
        assert raised

    @pytest.mark.asyncio
    async def test_explicit_none_also_fails(self, tmp_path):
        """Explicitly passing preflight_config=None still fails in production mode."""
        with pytest.raises(ProductionPreflightRequiredError):
            await collect_day(
                "TSLA", "2024-01-15", "2",
                output_dir=tmp_path,
                preflight_config=None,
            )


class TestDryRunBypassesPreflight:
    """dry_run=True skips preflight enforcement (unit test mode)."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_raise_preflight_required(self, tmp_path):
        """With dry_run=True and preflight_config=None, no enforcement error.

        The function will still try to connect to TradingView; we use the
        already-complete fast-path to avoid that by pre-writing a complete file.
        """
        from src.collector.day_collector import _output_path
        from src.collector.session_clock import session_end_timestamp

        # Write a complete file so the fast-path short-circuits before TV
        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        path = _output_path("TSLA", date, "2", tmp_path)
        _write_jsonl(path, [session_end_ts])

        # dry_run=True + no preflight_config → no ProductionPreflightRequiredError
        result = await collect_day(
            "TSLA", date, "2",
            output_dir=tmp_path,
            preflight_config=None,
            dry_run=True,
        )
        assert result.stop_reason == "already_complete"

    @pytest.mark.asyncio
    async def test_dry_run_true_skips_enforcement_check(self, tmp_path):
        """dry_run=True is the explicit escape hatch for unit test mode."""
        from src.collector.day_collector import _output_path
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        path = _output_path("TSLA", date, "2", tmp_path)
        _write_jsonl(path, [session_end_ts])

        # No exception raised
        result = await collect_day(
            "TSLA", date, "2",
            output_dir=tmp_path,
            dry_run=True,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_dry_run_false_still_enforces(self, tmp_path):
        """dry_run=False (explicitly set) still enforces preflight requirement."""
        with pytest.raises(ProductionPreflightRequiredError):
            await collect_day(
                "TSLA", "2024-01-15", "2",
                output_dir=tmp_path,
                dry_run=False,
            )


# ---------------------------------------------------------------------------
# Stale Collection Rejection
# ---------------------------------------------------------------------------

class TestRequireValidCollection:
    """require_valid_collection() raises StaleCollectionError for invalid collections."""

    def test_missing_companion_raises(self, tmp_path):
        """No companion file → StaleCollectionError."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        with pytest.raises(StaleCollectionError, match="no preflight companion"):
            require_valid_collection(jsonl)

    def test_missing_companion_error_names_expected_file(self, tmp_path):
        """Error message includes the expected companion filename."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        with pytest.raises(StaleCollectionError, match="TSLA_2024-01-15_2m_preflight.json"):
            require_valid_collection(jsonl)

    def test_companion_preflight_passed_false_raises(self, tmp_path):
        """Companion with preflight_passed=False → StaleCollectionError."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text(json.dumps({
            "preflight_passed": False,
            "failure_reasons": ["required indicator missing: 'Stop Loss Widget'"],
        }))
        with pytest.raises(StaleCollectionError, match="preflight_passed=False"):
            require_valid_collection(jsonl)

    def test_corrupt_companion_raises(self, tmp_path):
        """Corrupt/unreadable companion → StaleCollectionError."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text("not valid json {{{")
        with pytest.raises(StaleCollectionError, match="corrupt"):
            require_valid_collection(jsonl)

    def test_valid_companion_does_not_raise(self, tmp_path):
        """Valid companion with preflight_passed=True → no exception."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        result = _preflight_result(passed=True)
        write_preflight_companion(result, jsonl)
        require_valid_collection(jsonl)  # no exception

    def test_companion_missing_key_treated_as_failed(self, tmp_path):
        """Companion with no preflight_passed key → StaleCollectionError."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        jsonl.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text(json.dumps({"template_name": "only KCU indicator"}))
        with pytest.raises(StaleCollectionError):
            require_valid_collection(jsonl)


class TestStaleCollectionCannotBeReplayed:
    """BacktestReplay.from_validated_path() refuses stale collections."""

    def test_from_validated_path_raises_for_missing_companion(self, tmp_path):
        """No companion → StaleCollectionError before any replay is created."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000, 1700000120])
        with pytest.raises(StaleCollectionError):
            BacktestReplay.from_validated_path(jsonl)

    def test_from_validated_path_raises_for_failed_preflight(self, tmp_path):
        """Failed companion → StaleCollectionError."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000, 1700000120])
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text(json.dumps({
            "preflight_passed": False,
            "failure_reasons": ["required indicator missing: 'Volume'"],
        }))
        with pytest.raises(StaleCollectionError):
            BacktestReplay.from_validated_path(jsonl)

    def test_from_validated_path_succeeds_with_valid_companion(self, tmp_path):
        """Valid companion → BacktestReplay created successfully."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000, 1700000120])
        result = _preflight_result(passed=True)
        write_preflight_companion(result, jsonl)
        replay = BacktestReplay.from_validated_path(jsonl)
        assert replay.total_candles == 2

    def test_from_path_still_loads_without_companion(self, tmp_path):
        """from_path() (non-validated) still works — for tests using synthetic JSONL."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000, 1700000120])
        replay = BacktestReplay.from_path(jsonl)
        assert replay.total_candles == 2

    def test_from_validated_path_is_forward_only(self, tmp_path):
        """Validated path produces a proper BacktestReplay (forward-only guard active)."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000, 1700000120])
        result = _preflight_result(passed=True)
        write_preflight_companion(result, jsonl)
        replay = BacktestReplay.from_validated_path(jsonl)
        with pytest.raises(LookaheadGuardError):
            replay.previous()

    def test_stale_collection_error_message_names_collection(self, tmp_path):
        """StaleCollectionError message includes the JSONL filename."""
        jsonl = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_jsonl(jsonl, [1700000000])
        with pytest.raises(StaleCollectionError, match="TSLA_2024-01-15_2m.jsonl"):
            BacktestReplay.from_validated_path(jsonl)


# ---------------------------------------------------------------------------
# Model Routing Config Validation
# ---------------------------------------------------------------------------

class TestModelRoutingConfig:
    """config/models.yaml must separate implementation_model from architecture_model."""

    @pytest.fixture(scope="class")
    @classmethod
    def config(cls):
        return yaml.safe_load(_MODELS_CONFIG.read_text())

    def test_config_file_exists(self):
        assert _MODELS_CONFIG.exists(), "config/models.yaml not found"

    def test_implementation_model_present(self, config):
        assert "implementation_model" in config

    def test_architecture_model_present(self, config):
        assert "architecture_model" in config

    def test_implementation_model_is_ollama_cloud(self, config):
        impl = config["implementation_model"]
        assert impl["provider"] == "ollama-cloud"

    def test_implementation_model_is_not_claude(self, config):
        impl = config["implementation_model"]
        assert impl["provider"] != "claude"

    def test_architecture_model_is_claude(self, config):
        arch = config["architecture_model"]
        assert arch["provider"] == "claude"

    def test_routing_implementation_goes_to_implementation_model(self, config):
        assert config["routing"]["implementation"] == "implementation_model"

    def test_routing_architecture_goes_to_architecture_model(self, config):
        assert config["routing"]["architecture"] == "architecture_model"

    def test_routing_trade_simulation_goes_to_implementation_model(self, config):
        assert config["routing"].get("trade_simulation") == "implementation_model"

    def test_implementation_model_has_fallback_order(self, config):
        impl = config["implementation_model"]
        assert "fallback_order" in impl
        assert len(impl["fallback_order"]) >= 1

    def test_implementation_model_primary_is_glm(self, config):
        impl = config["implementation_model"]
        assert "glm" in impl["model"].lower()

    def test_implementation_model_has_signin_command(self, config):
        impl = config["implementation_model"]
        assert "signin_command" in impl

    def test_policies_preflight_mandatory(self, config):
        assert config["policies"].get("preflight_mandatory") is True

    def test_policies_implementation_by_worker_model(self, config):
        assert config["policies"].get("implementation_by_worker_model") is True

    def test_architecture_model_has_scope_field(self, config):
        arch = config["architecture_model"]
        assert "scope" in arch

    def test_review_model_is_not_claude(self, config):
        review = config["review_model"]
        assert review.get("provider") != "claude"
