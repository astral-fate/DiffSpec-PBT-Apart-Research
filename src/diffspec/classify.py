"""Disagreement taxonomy.

Five categories cover the gaps we observe between LLM-generated specs:

    OVERSPEC          - a spec rejects an output that the other accepts; the
                        rejecting spec is too strong.
    UNDERSPEC         - a spec accepts a clearly-wrong (mutated) output; the
                        accepting spec is too weak.
    PRECOND_MISMATCH  - specs disagree about which inputs are valid.
    EDGE_DRIFT        - disagreement only on edge inputs (empty, None,
                        boundary sizes). Useful diagnostic; usually a
                        sub-case of underspec or overspec restricted to the
                        edge of the input domain.
    CRASH             - one spec raises on an input the other handles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DisagreementType(str, Enum):
    OVERSPEC = "OVERSPEC"
    UNDERSPEC = "UNDERSPEC"
    PRECOND_MISMATCH = "PRECOND_MISMATCH"
    EDGE_DRIFT = "EDGE_DRIFT"
    CRASH = "CRASH"


@dataclass(frozen=True)
class Disagreement:
    """A concrete witness that two specs disagree."""

    type: DisagreementType
    check: str             # "soundness" | "uniqueness" | "precondition"
    input_val: Any
    output_val: Any | None
    spec_a_verdict: bool | None
    spec_b_verdict: bool | None
    spec_a_name: str
    spec_b_name: str
    explanation: str

    def short(self) -> str:
        return (
            f"[{self.type.value}] {self.check}: "
            f"{self.spec_a_name}={self.spec_a_verdict} vs "
            f"{self.spec_b_name}={self.spec_b_verdict} "
            f"on input={self.input_val!r}"
            + (f" output={self.output_val!r}" if self.output_val is not None else "")
        )


def _is_edge_input(i: Any) -> bool:
    """Heuristic: is this input a boundary case?"""

    if i is None:
        return True
    if isinstance(i, (list, str, tuple, bytes)) and len(i) == 0:
        return True
    if isinstance(i, dict) and len(i) == 0:
        return True
    if isinstance(i, tuple) and any(_is_edge_input(x) for x in i):
        return True
    if isinstance(i, int) and (i == 0 or abs(i) > 10**6):
        return True
    return False


def classify(
    check: str,
    spec_a_verdict: bool | None,
    spec_b_verdict: bool | None,
    input_val: Any,
    output_val: Any | None,
    spec_a_name: str,
    spec_b_name: str,
    crashed: str | None = None,
) -> Disagreement:
    """Map a raw differ result into a typed Disagreement.

    `crashed` is the name of the spec that raised, if any.
    """

    if crashed is not None:
        return Disagreement(
            type=DisagreementType.CRASH,
            check=check,
            input_val=input_val,
            output_val=output_val,
            spec_a_verdict=spec_a_verdict,
            spec_b_verdict=spec_b_verdict,
            spec_a_name=spec_a_name,
            spec_b_name=spec_b_name,
            explanation=f"spec {crashed!r} raised an exception on this input/output",
        )

    if check == "precondition":
        t = DisagreementType.PRECOND_MISMATCH
        expl = (
            f"specs disagree on whether input is valid: "
            f"{spec_a_name}.pre={spec_a_verdict}, {spec_b_name}.pre={spec_b_verdict}"
        )
    elif check == "soundness":
        # One spec accepts the implementation's output, the other rejects.
        # The rejecting spec is OVERspecified (it disallows a real output
        # of the implementation we deemed correct).
        if _is_edge_input(input_val):
            t = DisagreementType.EDGE_DRIFT
        else:
            t = DisagreementType.OVERSPEC
        rejecter = spec_a_name if spec_a_verdict is False else spec_b_name
        expl = (
            f"implementation output rejected by {rejecter!r} but accepted by the other; "
            f"the rejecter is OVERspecified"
        )
    elif check == "uniqueness":
        # A mutated output is accepted by one spec, rejected by the other.
        # The accepting spec is UNDERspecified.
        if _is_edge_input(input_val):
            t = DisagreementType.EDGE_DRIFT
        else:
            t = DisagreementType.UNDERSPEC
        accepter = spec_a_name if spec_a_verdict else spec_b_name
        expl = (
            f"mutated output accepted by {accepter!r} but rejected by the other; "
            f"the accepter is UNDERspecified"
        )
    else:  # pragma: no cover - defensive
        t = DisagreementType.OVERSPEC
        expl = f"unknown check {check!r}"

    return Disagreement(
        type=t,
        check=check,
        input_val=input_val,
        output_val=output_val,
        spec_a_verdict=spec_a_verdict,
        spec_b_verdict=spec_b_verdict,
        spec_a_name=spec_a_name,
        spec_b_name=spec_b_name,
        explanation=expl,
    )
