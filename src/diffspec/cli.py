"""Command-line entry point.

Usage:
    python -m diffspec run               # fixture mode, all tasks
    python -m diffspec run --task sort   # one task
    python -m diffspec run --live        # regenerate via live APIs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# When invoked as `python -m diffspec.cli` ensure repo root is importable.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from evals.run_evals import run_all  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="diffspec", description="DiffSpec-PBT runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run the benchmark")
    run.add_argument("--task", default=None, help="only run a single task name")
    run.add_argument("--live", action="store_true", help="use live LLM mode")
    run.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    run.add_argument(
        "--benchmark",
        default=str(_REPO / "benchmark"),
        help="path to benchmark directory",
    )

    args = p.parse_args(argv)
    if args.cmd == "run":
        summary = run_all(
            benchmark_root=args.benchmark,
            task_filter=args.task,
            live=args.live,
            print_table=not args.json,
        )
        if args.json:
            print(json.dumps(summary, indent=2, default=str))
        return 0 if summary["tasks_with_drift"] > 0 else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
