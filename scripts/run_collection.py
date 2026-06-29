"""Run one complete day collection for TSLA.

Usage:
    python scripts/run_collection.py --ticker TSLA --date 2026-06-22 --timeframe 2

Runs preflight, then collects candles via TradingView replay.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.chart_preflight import load_preflight_config
from src.collector.day_collector import collect_day
from src.collector.workspace_preflight import load_workspace_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("run_collection")


async def main(ticker: str, date: str, timeframe: str) -> None:
    preflight_config = load_preflight_config()
    workspace_config = load_workspace_config()

    log.info("Starting collection: %s %s @ %sm", ticker, date, timeframe)
    result = await collect_day(
        ticker=ticker,
        date=date,
        timeframe=timeframe,
        output_dir=PROJECT_ROOT / "outputs" / "candles",
        preflight_config=preflight_config,
        workspace_config=workspace_config,
    )

    print(f"\n{'='*60}")
    print(f"Collection result: {result.stop_reason}")
    print(f"  Candles written:  {result.candles_written}")
    print(f"  Candles skipped:  {result.candles_skipped}")
    print(f"  Complete:         {result.complete}")
    print(f"  Output:           {result.output_path}")
    if result.preflight_metadata:
        print(f"  Preflight:        passed={result.preflight_metadata.get('preflight_passed')}  "
              f"warning={result.preflight_metadata.get('preflight_warning')}  "
              f"template={result.preflight_metadata.get('template_name')!r}")
    if result.validation_errors:
        print(f"  Validation errors: {result.validation_errors}")
        sys.exit(1)
    print("="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="TSLA")
    parser.add_argument("--date", default="2026-06-22")
    parser.add_argument("--timeframe", default="2")
    args = parser.parse_args()
    asyncio.run(main(args.ticker, args.date, args.timeframe))
