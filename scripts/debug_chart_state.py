"""Debug script: dumps the complete raw MCP chart_get_state payload.

Run from project root:
    python scripts/debug_chart_state.py

Saves everything to outputs/debug/chart_state_<timestamp>.json.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make project src importable
PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.tv_client import TradingViewClient


OUTPUT_DIR = PROJECT_ROOT / "outputs" / "debug"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    print("Connecting to tradingview-mcp server...")

    async with TradingViewClient() as client:
        # 1. List all available tools
        print("\n--- Available MCP tools ---")
        tools = await client.list_tools()
        for t in sorted(tools):
            print(f"  {t}")

        # 2. Call chart_get_state and capture raw result
        print("\n--- Calling chart_get_state ---")
        chart_state = await client.call_tool("chart_get_state", {})
        print(json.dumps(chart_state, indent=2, default=str))

        # 3. Analyse what preflight sees
        print("\n--- Preflight analysis ---")
        template_name = (
            chart_state.get("template_name") or chart_state.get("template")
        )
        print(f"template_name field:  {template_name!r}")
        print(f"template field:       {chart_state.get('template')!r}")
        print(f"All top-level keys:   {list(chart_state.keys())}")

        studies = chart_state.get("studies") or chart_state.get("indicators") or []
        print(f"\nstudies count: {len(studies)}")
        print("studies:")
        for s in studies:
            print(f"  {s}")

        # Extract indicator names as preflight._extract_indicators does
        names = []
        for item in studies:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("title") or "").strip()
                if name:
                    names.append(name)
            elif isinstance(item, str) and item.strip():
                names.append(item.strip())

        print(f"\nExtracted indicator names: {names}")
        names_lower = {n.lower() for n in names}
        print(f"Lower-cased names: {names_lower}")

        # Check against config
        kcu_keys = [
            "KCU Indicator", "KCU", "KCU_Indicator",
            "KCU Backtesting", "KCU Strategy",
        ]
        kcu_keys_lower = {k.lower() for k in kcu_keys}
        kcu_match = names_lower & kcu_keys_lower
        print(f"\nKCU key match: {kcu_match}")

        required = ["Stop Loss Widget", "KCU Indicator", "Volume"]
        effective = set(names_lower)
        if kcu_match:
            effective.add("kcu indicator")

        print("\nRequired indicator check:")
        for req in required:
            present = req.lower() in effective
            print(f"  {'✓' if present else '✗'} {req!r}")

        # 4. Try to call symbol_info for extra context
        print("\n--- Calling symbol_info ---")
        try:
            symbol_info = await client.call_tool("symbol_info", {})
            print(json.dumps(symbol_info, indent=2, default=str))
        except Exception as e:
            symbol_info = {"error": str(e)}
            print(f"symbol_info failed: {e}")

        # 5. Save complete payload
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"chart_state_{timestamp}.json"
        payload = {
            "timestamp": timestamp,
            "available_tools": tools,
            "chart_get_state_raw": chart_state,
            "symbol_info_raw": symbol_info,
            "debug_analysis": {
                "template_name_field": template_name,
                "all_top_level_keys": list(chart_state.keys()),
                "extracted_indicator_names": names,
                "kcu_key_match": list(kcu_match),
                "required_indicators_check": {
                    req: req.lower() in effective for req in required
                },
            },
        }
        output_path.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\n--- Saved to {output_path} ---")

        # 6. Diagnosis summary
        print("\n=== DIAGNOSIS SUMMARY ===")
        if template_name is None:
            print(
                "CONFIRMED: chart_get_state never returns template_name.\n"
                "  getState() in core/chart.js only emits: symbol, resolution,\n"
                "  chartType, studies[]. No template field is ever set.\n"
                "  → Template validation must be relaxed or made optional."
            )
        else:
            print(f"Template returned: {template_name!r}")

        missing_required = [req for req in required if req.lower() not in effective]
        if missing_required:
            print(f"\nMissing required indicators: {missing_required}")
            print(f"  Actual indicator names on chart: {names}")
            print(
                "  Either:\n"
                "  (a) These indicators are genuinely not on the chart, OR\n"
                "  (b) Their names differ from what config/chart_template.yaml expects."
            )
        else:
            print("\nAll required indicators present (by name match).")


if __name__ == "__main__":
    asyncio.run(main())
