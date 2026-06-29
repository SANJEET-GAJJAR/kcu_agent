#!/usr/bin/env python3
"""CLI: dispatch an implementation task to the configured implementation_model.

Usage:
    python scripts/route_task.py --task implement_outcome_simulation --prompt "Write ..."
    python scripts/route_task.py --task boilerplate --prompt-file prompts/outcome.txt
    echo "Write src/simulator/outcome.py" | python scripts/route_task.py --task implement_outcome_simulation

Exit codes:
    0  success
    1  model unavailable (all configured models failed)
    2  config error (models.yaml missing or malformed)
    3  Claude route attempt blocked
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path when run directly
_PROJECT_ROOT = Path(__file__).parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.router.config_loader import RouterConfigError, load_router_config
from src.router.dispatch import ClaudeRouteAttemptError, ModelUnavailableError, dispatch


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dispatch an implementation task to the configured model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--task", required=True, help="Short task identifier (logged)")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--prompt", help="Prompt text")
    group.add_argument("--prompt-file", type=Path, help="File containing the prompt")
    p.add_argument("--config", type=Path, help="Override config/models.yaml path")
    p.add_argument("--log-dir", type=Path, help="Override log output directory")
    p.add_argument("--dry-run", action="store_true", help="Print config and exit without dispatching")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_router_config(args.config)
    except RouterConfigError as exc:
        print(f"ERROR config: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        impl = config.implementation_model
        print(f"implementation_model: {impl.provider} / {impl.model}")
        print(f"command: {impl.command}")
        print(f"fallbacks: {len(config.fallback_order)}")
        return 0

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        if not args.prompt_file.exists():
            print(f"ERROR: prompt file not found: {args.prompt_file}", file=sys.stderr)
            return 2
        prompt = args.prompt_file.read_text()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print("ERROR: provide --prompt, --prompt-file, or pipe prompt via stdin", file=sys.stderr)
        return 2

    try:
        output = dispatch(args.task, prompt, config, log_dir=args.log_dir)
        print(output, end="")
        return 0
    except ClaudeRouteAttemptError as exc:
        print(f"ERROR blocked: {exc}", file=sys.stderr)
        return 3
    except ModelUnavailableError as exc:
        print(f"ERROR unavailable: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
