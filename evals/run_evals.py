"""Evaluation harness.

Walks ``benchmark/``, loads each task's two fixture specs, the
implementation, and the input/output Hypothesis strategies, and runs
the Differ. Writes ``evals/results.json`` and prints a headline table.
"""

from __future__ import annotations

import json
import sys
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from diffspec.differ import Differ
from diffspec.llm import FixtureProvider, LiveProvider, SpecProvider
from diffspec.report import Report, summarize
from diffspec.specs import load_spec_from_source


def _load_module(path: Path, module_name: str):
    spec = spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_tasks(benchmark_root: Path) -> list[Path]:
    return sorted(
        d for d in benchmark_root.iterdir()
        if d.is_dir() and (d / "requirement.md").exists()
    )


def run_one_task(
    task_dir: Path,
    provider: SpecProvider,
    models: tuple[str, str] = ("qwen", "llama"),
) -> Report:
    name = task_dir.name
    impl_mod = _load_module(task_dir / "impl.py", f"impl_{name}")
    strat_mod = _load_module(task_dir / "strategy.py", f"strategy_{name}")

    src_a = provider.get(name, models[0]).source
    src_b = provider.get(name, models[1]).source
    spec_a = load_spec_from_source(models[0], src_a, origin=str(task_dir))
    spec_b = load_spec_from_source(models[1], src_b, origin=str(task_dir))

    differ = Differ()
    t0 = time.perf_counter()
    results = differ.diff(
        spec_a, spec_b,
        impl=impl_mod.impl,
        input_strategy=strat_mod.input_strategy,
        output_strategy=getattr(strat_mod, "output_strategy", None),
    )
    elapsed = time.perf_counter() - t0
    return Report(
        task=name,
        spec_a_name=models[0],
        spec_b_name=models[1],
        results=results,
        elapsed_seconds=elapsed,
    )


_KNOWN_MODELS = ("qwen", "llama", "gpt-oss", "compound")


def _available_models_for_task(task_dir: Path) -> list[str]:
    """Return the model aliases whose fixture file exists AND parses."""
    import ast

    out: list[str] = []
    for m in _KNOWN_MODELS:
        f = task_dir / "fixtures" / f"{m}.py"
        if not f.exists():
            continue
        try:
            src = f.read_text(encoding="utf-8")
            ast.parse(src)
            if "def pre" in src and "def post" in src:
                out.append(m)
        except SyntaxError:
            continue
    return out


def run_all(
    benchmark_root: str | Path | None = None,
    task_filter: Optional[str] = None,
    live: bool = False,
    print_table: bool = True,
    pair: Optional[tuple[str, str]] = None,
) -> dict:
    """Run pairwise differential checks across all available model pairs.

    If ``pair`` is given, run only that one pair (back-compat with the
    original two-model headline). Otherwise, run all C(N,2) pairs for
    whatever models have parseable fixtures.
    """
    root = Path(benchmark_root) if benchmark_root else (_REPO / "benchmark")
    provider: SpecProvider = LiveProvider(root) if live else FixtureProvider(root)

    tasks = discover_tasks(root)
    if task_filter:
        tasks = [t for t in tasks if task_filter in t.name]

    pair_reports: list[Report] = []  # one Report per (task, pair)
    for task_dir in tasks:
        avail = _available_models_for_task(task_dir)
        if pair is not None:
            pairs = [pair] if pair[0] in avail and pair[1] in avail else []
        else:
            pairs = [(a, b) for i, a in enumerate(avail) for b in avail[i + 1:]]
        for a, b in pairs:
            try:
                r = run_one_task(task_dir, provider, models=(a, b))
            except Exception as exc:
                print(f"  ! {task_dir.name} [{a}|{b}]: failed ({exc!r})")
                continue
            pair_reports.append(r)

    summary = _nway_summary(pair_reports, tasks)

    if print_table:
        _print_nway_table(pair_reports, summary)

    out = _REPO / "evals" / "results.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    if print_table:
        print(f"\nresults written to {out}")

    return summary


def _nway_summary(pair_reports: list[Report], task_dirs: list[Path]) -> dict:
    """Aggregate per-pair Reports into a tasks-x-pairs summary."""
    base = summarize(pair_reports)
    # Per-task: did ANY pair detect drift?
    by_task: dict[str, dict] = {}
    for r in pair_reports:
        e = by_task.setdefault(
            r.task,
            {
                "task": r.task,
                "available_models": _available_models_for_task(
                    next(d for d in task_dirs if d.name == r.task)
                ),
                "pairs_evaluated": 0,
                "pairs_with_drift": 0,
                "any_drift": False,
                "drift_types": set(),
                "pair_results": [],
            },
        )
        e["pairs_evaluated"] += 1
        if r.found:
            e["pairs_with_drift"] += 1
            e["any_drift"] = True
            for d in r.disagreements:
                e["drift_types"].add(d.type.value)
        e["pair_results"].append(
            {
                "pair": f"{r.spec_a_name}-{r.spec_b_name}",
                "found": r.found,
                "types": sorted({d.type.value for d in r.disagreements}),
                "elapsed_seconds": round(r.elapsed_seconds, 3),
                "examples_to_first": next(
                    (cr.examples_tried for cr in r.results if cr.disagreement),
                    None,
                ),
            }
        )

    tasks_any_drift = sum(1 for v in by_task.values() if v["any_drift"])

    # Per-pair counters
    per_pair: dict[str, dict] = {}
    for r in pair_reports:
        key = f"{r.spec_a_name}-{r.spec_b_name}"
        p = per_pair.setdefault(key, {"tasks_evaluated": 0, "tasks_with_drift": 0})
        p["tasks_evaluated"] += 1
        if r.found:
            p["tasks_with_drift"] += 1

    base.update(
        {
            "tasks_total": len(by_task),
            "tasks_with_any_drift": tasks_any_drift,
            "tasks_drift_rate": tasks_any_drift / max(1, len(by_task)),
            "by_pair": per_pair,
            "tasks_detail": [
                {**v, "drift_types": sorted(v["drift_types"])}
                for v in by_task.values()
            ],
        }
    )
    return base


def _print_nway_table(pair_reports: list[Report], summary: dict) -> None:
    by_task: dict[str, list[Report]] = {}
    for r in pair_reports:
        by_task.setdefault(r.task, []).append(r)
    print(f"\n{'task':<24} {'pair':<22} {'drift':<6} {'types':<24} {'pbt':<5} {'time':<6}")
    print("-" * 90)
    for task_name in sorted(by_task):
        for r in by_task[task_name]:
            types = ", ".join(sorted({d.type.value for d in r.disagreements})) or "-"
            first = ""
            for cr in r.results:
                if cr.disagreement is not None:
                    first = str(cr.examples_tried)
                    break
            print(
                f"{r.task:<24} "
                f"{r.spec_a_name + '-' + r.spec_b_name:<22} "
                f"{'YES' if r.found else 'no':<6} "
                f"{types[:22]:<24} "
                f"{first:<5} "
                f"{r.elapsed_seconds:5.2f}s"
            )
    print("=" * 90)
    print(
        f"Tasks where ANY pair detected drift: "
        f"{summary['tasks_with_any_drift']}/{summary['tasks_total']} "
        f"({summary['tasks_drift_rate']:.0%})"
    )
    print("\nPer-pair drift counts:")
    for pair, p in summary["by_pair"].items():
        print(f"  {pair:<28} {p['tasks_with_drift']}/{p['tasks_evaluated']}")
    print(f"\nDisagreement distribution across all pairs:")
    for t, n in summary["by_type"].items():
        if n:
            print(f"  {t:<20} {n}")
    if summary.get("median_examples_to_first_disagreement") is not None:
        print(f"Median PBT examples to first disagreement: "
              f"{summary['median_examples_to_first_disagreement']}")
    print("=" * 90)


def _print_table(reports: list[Report], summary: dict) -> None:
    print(f"\n{'task':<24} {'drift':<6} {'types':<28} {'pbt':<6} {'time':<7}")
    print("-" * 78)
    for r in reports:
        types = ", ".join(sorted({d.type.value for d in r.disagreements})) or "-"
        types = types[:26]
        first_examples = ""
        for cr in r.results:
            if cr.disagreement is not None:
                first_examples = str(cr.examples_tried)
                break
        print(
            f"{r.task:<24} "
            f"{'YES' if r.found else 'no':<6} "
            f"{types:<28} "
            f"{first_examples:<6} "
            f"{r.elapsed_seconds:6.2f}s"
        )
    print("=" * 78)
    print(f"Tasks with intent drift detected: "
          f"{summary['tasks_with_drift']}/{summary['total_tasks']}  "
          f"({summary['drift_rate']:.0%})")
    print("Disagreement distribution:")
    for t, n in summary["by_type"].items():
        if n:
            print(f"  {t:<20} {n}")
    if summary["median_examples_to_first_disagreement"] is not None:
        print(f"Median PBT examples to first disagreement: "
              f"{summary['median_examples_to_first_disagreement']}")
    print("=" * 78)


if __name__ == "__main__":
    raise SystemExit(0 if run_all()["tasks_with_drift"] > 0 else 1)
