"""Structured per-task report and benchmark-wide summary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from diffspec.classify import Disagreement, DisagreementType
from diffspec.differ import CheckResult


@dataclass
class Report:
    """Per-task report aggregating the three checks."""

    task: str
    spec_a_name: str
    spec_b_name: str
    results: List[CheckResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    load_errors: List[str] = field(default_factory=list)

    @property
    def disagreements(self) -> List[Disagreement]:
        return [r.disagreement for r in self.results if r.disagreement is not None]

    @property
    def found(self) -> bool:
        return bool(self.disagreements)

    @property
    def types(self) -> set[DisagreementType]:
        return {d.type for d in self.disagreements}

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "spec_a": self.spec_a_name,
            "spec_b": self.spec_b_name,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "load_errors": list(self.load_errors),
            "checks": [
                {
                    "check": r.check,
                    "examples_tried": r.examples_tried,
                    "disagreement": (
                        None
                        if r.disagreement is None
                        else {
                            "type": r.disagreement.type.value,
                            "input": repr(r.disagreement.input_val),
                            "output": (
                                None
                                if r.disagreement.output_val is None
                                else repr(r.disagreement.output_val)
                            ),
                            "spec_a_verdict": r.disagreement.spec_a_verdict,
                            "spec_b_verdict": r.disagreement.spec_b_verdict,
                            "explanation": r.disagreement.explanation,
                        }
                    ),
                }
                for r in self.results
            ],
        }


def summarize(reports: List[Report]) -> dict:
    """Aggregate per-task reports into a benchmark summary."""

    total = len(reports)
    with_drift = sum(1 for r in reports if r.found)
    by_type: dict[str, int] = {t.value: 0 for t in DisagreementType}
    examples_to_first: list[int] = []

    for r in reports:
        for d in r.disagreements:
            by_type[d.type.value] += 1
        if r.found:
            # Examples-tried in the first check that produced a disagreement
            for cr in r.results:
                if cr.disagreement is not None:
                    examples_to_first.append(cr.examples_tried)
                    break

    median_first = (
        sorted(examples_to_first)[len(examples_to_first) // 2]
        if examples_to_first
        else None
    )

    tasks_with_load_error = sum(1 for r in reports if r.load_errors)

    return {
        "total_tasks": total,
        "tasks_with_drift": with_drift,
        "tasks_with_load_error": tasks_with_load_error,
        "drift_rate": with_drift / total if total else 0.0,
        "by_type": by_type,
        "median_examples_to_first_disagreement": median_first,
        "tasks": [r.to_dict() for r in reports],
    }
