"""Chart preflight — validates TradingView chart environment before collection.

Verifies the chart is using the correct template and all required indicators
are present before any candle collection begins.

Required indicators:
  - Stop Loss Widget
  - KCU Indicator (any name from kcu_indicator_keys)
  - Volume

On failure:
  - Raises PreflightFailedError
  - Writes preflight_failed.json to the output directory
  - Collection must not proceed

On success:
  - Returns PreflightResult with preflight_passed=True
  - Companion file {collection_stem}_preflight.json should be written
    alongside the JSONL by the caller

Collections without a valid preflight companion file are considered
stale/invalid and cannot be backtested.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_DEFAULT_CHART_TEMPLATE_PATH = (
    Path(__file__).parents[2] / "config" / "chart_template.yaml"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PreflightFailedError(Exception):
    """Raised when chart preflight fails — collection must not proceed."""


class StaleCollectionError(Exception):
    """Raised when a collection lacks a valid preflight companion file.

    A collection is stale (invalid for backtest) when:
      - The preflight companion file is missing, OR
      - The companion file contains preflight_passed=False, OR
      - The companion file is corrupt/unreadable.

    Stale collections were gathered without the mandatory preflight check.
    They cannot be used for backtesting.
    """


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ChartPreflightConfig:
    """Loaded from config/chart_template.yaml."""
    required_template: str
    required_indicators: list[str]
    kcu_indicator_keys: list[str]
    chart_state_tool: str
    collection_version: str
    collector_version: str
    preflight_failed_filename: str = "preflight_failed.json"

    def __post_init__(self) -> None:
        if not self.required_template:
            raise ValueError("required_template must not be empty")
        if not self.required_indicators:
            raise ValueError("required_indicators must not be empty")
        if not self.kcu_indicator_keys:
            raise ValueError("kcu_indicator_keys must not be empty")
        if not self.collection_version:
            raise ValueError("collection_version must not be empty")
        if not self.collector_version:
            raise ValueError("collector_version must not be empty")


def load_preflight_config(
    path: Path | str | None = None,
) -> ChartPreflightConfig:
    """Load ChartPreflightConfig from chart_template.yaml."""
    config_path = Path(path) if path else _DEFAULT_CHART_TEMPLATE_PATH
    with open(config_path) as f:
        data = yaml.safe_load(f)

    return ChartPreflightConfig(
        required_template=str(data["required_template"]),
        required_indicators=[str(x) for x in data["required_indicators"]],
        kcu_indicator_keys=[str(x) for x in data["kcu_indicator_keys"]],
        chart_state_tool=str(data.get("chart_state_tool", "chart_get_state")),
        collection_version=str(data.get("collection_version", "1.0.0")),
        collector_version=str(data.get("collector_version", "1.0.0")),
        preflight_failed_filename=str(
            data.get("preflight_failed_filename", "preflight_failed.json")
        ),
    )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class PreflightResult:
    """Result of one preflight validation run."""
    template_name: str | None
    indicator_names: list[str]
    required_indicators_present: bool
    kcu_indicator_version: str      # "unknown" if not detectable but indicator exists
    preflight_passed: bool
    collection_version: str
    collector_version: str
    failure_reasons: list[str] = field(default_factory=list)
    # True when template_name could not be verified (MCP protocol limitation).
    # Only set when all required indicators ARE confirmed present.
    preflight_warning: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_metadata(self) -> dict[str, Any]:
        """Subset of result fields written as collection metadata."""
        return {
            "template_name": self.template_name,
            "indicator_names": self.indicator_names,
            "required_indicators_present": self.required_indicators_present,
            "kcu_indicator_version": self.kcu_indicator_version,
            "preflight_passed": self.preflight_passed,
            "preflight_warning": self.preflight_warning,
            "collection_version": self.collection_version,
            "collector_version": self.collector_version,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.collection_version:
            errors.append("collection_version must not be empty")
        if not self.collector_version:
            errors.append("collector_version must not be empty")
        if self.kcu_indicator_version == "":
            errors.append(
                "kcu_indicator_version must not be empty "
                "(use 'unknown' if version is undetectable)"
            )
        return errors


# ---------------------------------------------------------------------------
# Preflight engine
# ---------------------------------------------------------------------------

class ChartPreflight:
    """Validates TradingView chart environment against chart_template.yaml.

    Pure validation (no TradingView):
        config = load_preflight_config()
        pf = ChartPreflight(config)
        result = pf.validate(chart_state_dict)

    Full preflight with TradingView:
        async with TradingViewClient() as client:
            result = await pf.run(client, output_dir)
            # raises PreflightFailedError if validation fails
    """

    def __init__(self, config: ChartPreflightConfig) -> None:
        self._config = config

    def validate(self, chart_state: dict[str, Any]) -> PreflightResult:
        """Validate a chart state dict against configured requirements.

        Expected chart_state format (from chart_get_state MCP tool):
            {
                "success": true,
                "template_name": "only KCU indicator",
                "studies": [
                    {"name": "Stop Loss Widget", "version": null},
                    {"name": "KCU Indicator", "version": "1.2.3"},
                    {"name": "Volume", "version": null}
                ]
            }

        Also accepts "template" (alias) and "indicators" (alias for studies).
        Study items may be plain strings or dicts with "name"/"version".

        Returns PreflightResult. Raises nothing — caller decides on failure action.
        """
        failure_reasons: list[str] = []
        preflight_warning = False

        raw_template = (
            chart_state.get("template_name") or chart_state.get("template")
        )
        indicator_names, indicator_versions = _extract_indicators(chart_state)

        # --- Check 1: template name ---
        # MCP (chart_get_state) never returns a template_name field — it is a
        # protocol limitation of the tradingview-mcp server (core/chart.js only
        # emits symbol/resolution/chartType/studies).  When template_name is
        # None we cannot validate the template, so we record a warning and
        # defer the check.  If the name IS present but wrong, we fail hard.
        if raw_template is None:
            template_name = "unknown"
            preflight_warning = True
            log.warning(
                "template_name not returned by MCP (protocol limitation); "
                "skipping template check — preflight_warning=True will be recorded"
            )
        elif raw_template != self._config.required_template:
            template_name = raw_template
            failure_reasons.append(
                f"template must be {self._config.required_template!r}, "
                f"got {raw_template!r}"
            )
        else:
            template_name = raw_template

        # --- Check 2: required indicators ---
        # KCU indicator key matching uses substring search so that decorated
        # names such as "👑 KCU LTP Indicator - v1.4.1" are recognised when
        # "KCU LTP Indicator" appears in kcu_indicator_keys.
        effective_lower = {n.lower() for n in indicator_names}
        kcu_keys_lower = {k.lower() for k in self._config.kcu_indicator_keys}
        kcu_present = _kcu_substring_match(effective_lower, kcu_keys_lower)
        if kcu_present:
            effective_lower.add("kcu indicator")

        missing_indicators: list[str] = []
        for required in self._config.required_indicators:
            if required.lower() not in effective_lower:
                missing_indicators.append(required)
                failure_reasons.append(f"required indicator missing: {required!r}")

        required_indicators_present = len(missing_indicators) == 0

        # --- Check 3: KCU presence (explicit, separate from required list) ---
        if not kcu_present:
            # Already added via required_indicators if "KCU Indicator" is configured there.
            # Add separately if it wasn't already surfaced.
            kcu_missing_already_reported = any(
                "required indicator missing" in r
                and any(k.lower() in r.lower() for k in self._config.kcu_indicator_keys + ["kcu indicator"])
                for r in failure_reasons
            )
            if not kcu_missing_already_reported:
                failure_reasons.append(
                    f"KCU Indicator not found on chart "
                    f"(expected one of: {self._config.kcu_indicator_keys})"
                )

        # --- Check 4: KCU version detection ---
        kcu_version = _detect_kcu_version(
            indicator_names, indicator_versions, self._config.kcu_indicator_keys
        )
        # Unknown version is allowed as long as the indicator exists.
        # (No failure_reason added for unknown version.)

        preflight_passed = len(failure_reasons) == 0

        return PreflightResult(
            template_name=template_name,
            indicator_names=list(indicator_names),
            required_indicators_present=required_indicators_present,
            kcu_indicator_version=kcu_version,
            preflight_passed=preflight_passed,
            collection_version=self._config.collection_version,
            collector_version=self._config.collector_version,
            failure_reasons=failure_reasons,
            preflight_warning=preflight_warning,
        )

    async def run(
        self,
        client: Any,
        output_dir: Path,
    ) -> PreflightResult:
        """Run preflight against the live TradingView chart.

        Calls chart_get_state MCP tool. Writes preflight_failed.json and raises
        PreflightFailedError if any check fails. Never proceeds to collection
        on failure.

        Args:
            client:     Active TradingViewClient session.
            output_dir: Directory to write preflight_failed.json on failure.
        """
        log.info(
            "Running chart preflight via %r", self._config.chart_state_tool
        )

        try:
            chart_state = await client.call_tool(self._config.chart_state_tool, {})
        except Exception as exc:
            chart_state = {"success": False, "error": str(exc)}
            log.error("chart_get_state call failed: %s", exc)

        result = self.validate(chart_state)

        if not result.preflight_passed:
            log.error(
                "Chart preflight FAILED (%d reason(s)): %s",
                len(result.failure_reasons),
                result.failure_reasons,
            )
            _write_failure_file(result, output_dir, self._config.preflight_failed_filename)
            raise PreflightFailedError(
                f"Chart preflight failed ({len(result.failure_reasons)} reason(s)): "
                f"{result.failure_reasons}"
            )

        log.info(
            "Chart preflight PASSED: template=%r, KCU version=%r, indicators=%s",
            result.template_name,
            result.kcu_indicator_version,
            result.indicator_names,
        )
        return result


# ---------------------------------------------------------------------------
# Collection validation helpers
# ---------------------------------------------------------------------------

def validate_collection(collection_path: Path) -> bool:
    """Return True if the collection has a valid preflight companion file.

    Checks for {stem}_preflight.json alongside the JSONL with
    preflight_passed=True.

    Collections missing the companion file are considered invalid — they were
    collected before preflight was enforced or without running it.
    """
    preflight_path = _preflight_companion_path(collection_path)
    if not preflight_path.exists():
        return False
    try:
        data = json.loads(preflight_path.read_text())
        return data.get("preflight_passed") is True
    except Exception:
        return False


def require_valid_collection(collection_path: Path) -> None:
    """Assert a collection has a valid preflight companion file.

    Raises StaleCollectionError if the collection is missing a companion file
    with preflight_passed=True. Call this before any backtest replay to ensure
    the collection was gathered under the correct chart environment.

    Args:
        collection_path: Path to the JSONL collection file.

    Raises:
        StaleCollectionError: If the companion file is missing, has
            preflight_passed=False, or is corrupt.
    """
    preflight_path = _preflight_companion_path(collection_path)
    if not preflight_path.exists():
        raise StaleCollectionError(
            f"Collection {collection_path.name!r} has no preflight companion file. "
            "This collection was gathered without the mandatory chart preflight check "
            "and cannot be used for backtesting. "
            f"Expected: {preflight_path.name}"
        )
    try:
        data = json.loads(preflight_path.read_text())
    except Exception as exc:
        raise StaleCollectionError(
            f"Preflight companion file for {collection_path.name!r} is corrupt: {exc}"
        ) from exc

    if data.get("preflight_passed") is not True:
        reasons = data.get("failure_reasons", [])
        raise StaleCollectionError(
            f"Collection {collection_path.name!r} has preflight_passed=False "
            f"and cannot be used for backtesting. "
            f"Failure reasons: {reasons}"
        )


def write_preflight_companion(
    result: PreflightResult,
    collection_path: Path,
) -> Path:
    """Write preflight metadata alongside a collection JSONL file.

    Returns the path of the written companion file.
    """
    companion = _preflight_companion_path(collection_path)
    companion.parent.mkdir(parents=True, exist_ok=True)
    companion.write_text(json.dumps(result.to_dict(), indent=2))
    log.info("Preflight companion written to %s", companion)
    return companion


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_indicators(
    chart_state: dict[str, Any],
) -> tuple[list[str], dict[str, str | None]]:
    """Extract indicator names and versions from a chart state dict.

    Handles:
      - studies list of dicts with "name" and optional "version"/"ver"
      - studies list of plain strings
      - "indicators" as alias for "studies"

    Returns (names_in_order, name→version_or_None).
    """
    studies = chart_state.get("studies") or chart_state.get("indicators") or []
    names: list[str] = []
    versions: dict[str, str | None] = {}

    if isinstance(studies, list):
        for item in studies:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("title") or "").strip()
                raw_ver = item.get("version") or item.get("ver")
                version = str(raw_ver).strip() if raw_ver is not None else None
                if name:
                    names.append(name)
                    versions[name] = version or None
            elif isinstance(item, str) and item.strip():
                name = item.strip()
                names.append(name)
                versions[name] = None

    return names, versions


def _kcu_substring_match(names_lower: set[str], kcu_keys_lower: set[str]) -> bool:
    """Return True if any kcu_key is a substring of any indicator name (case-insensitive).

    Substring matching is required because TradingView may display indicator
    names with decorators and version suffixes, e.g. "👑 KCU LTP Indicator - v1.4.1".
    """
    return any(key in name for name in names_lower for key in kcu_keys_lower)


def _detect_kcu_version(
    indicator_names: list[str],
    indicator_versions: dict[str, str | None],
    kcu_keys: list[str],
) -> str:
    """Return the KCU indicator version string, or 'unknown' if undetectable.

    Uses substring matching so decorated names like "👑 KCU LTP Indicator - v1.4.1"
    are recognised when "KCU LTP Indicator" appears in kcu_keys.
    """
    kcu_keys_lower = [k.lower() for k in kcu_keys]
    for name in indicator_names:
        if any(key in name.lower() for key in kcu_keys_lower):
            version = indicator_versions.get(name)
            return version if version else "unknown"
    return "unknown"


def _write_failure_file(
    result: PreflightResult,
    output_dir: Path,
    filename: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    failure_path = output_dir / filename
    failure_path.write_text(json.dumps(result.to_dict(), indent=2))
    log.info("Preflight failure record written to %s", failure_path)


def _preflight_companion_path(collection_path: Path) -> Path:
    """Return the companion preflight JSON path for a collection JSONL."""
    return collection_path.with_name(collection_path.stem + "_preflight.json")
