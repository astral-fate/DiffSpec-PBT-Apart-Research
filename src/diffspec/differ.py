"""The DiffSpec Differ.

Runs three PBT-driven checks against a pair of specs:

  1. Soundness   - generate i, compute o = impl(i), compare post_A(i,o) vs
                   post_B(i,o). A disagreement here means one spec is
                   over-specified relative to the implementation.

  2. Uniqueness  - generate i and a mutated output o'. Compare post_A(i,o')
                   vs post_B(i,o'). A disagreement here means one spec is
                   under-specified.

  3. Precondition- generate i, compare pre_A(i) vs pre_B(i). A disagreement
                   here means the specs disagree about which inputs are
                   valid.

Each check returns at most one disagreement (Hypothesis's shrinking gives
us the minimal counterexample). The Differ as a whole collects up to
three disagreements (one per check) per spec pair per task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.errors import InvalidArgument

from diffspec.classify import (
    Disagreement,
    DisagreementType,
    classify,
)
from diffspec.specs import Spec


@dataclass(frozen=True)
class CheckResult:
    """Result of a single check: optional disagreement + counter examples seen."""

    check: str
    disagreement: Optional[Disagreement]
    examples_tried: int


class Differ:
    """Differential PBT engine for two specs of the same requirement."""

    def __init__(
        self,
        max_examples_soundness: int = 80,
        max_examples_uniqueness: int = 150,
        max_examples_precondition: int = 80,
    ) -> None:
        self.max_examples_soundness = max_examples_soundness
        self.max_examples_uniqueness = max_examples_uniqueness
        self.max_examples_precondition = max_examples_precondition

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diff(
        self,
        spec_a: Spec,
        spec_b: Spec,
        impl: Callable[[Any], Any],
        input_strategy: st.SearchStrategy,
        output_strategy: Optional[st.SearchStrategy] = None,
    ) -> List[CheckResult]:
        """Run all three checks. Returns a list of CheckResult (one per check)."""

        results: List[CheckResult] = []
        results.append(self._check_precondition(spec_a, spec_b, input_strategy))
        results.append(self._check_soundness(spec_a, spec_b, impl, input_strategy))
        if output_strategy is not None:
            results.append(
                self._check_uniqueness(spec_a, spec_b, input_strategy, output_strategy)
            )
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_precondition(
        self,
        spec_a: Spec,
        spec_b: Spec,
        input_strategy: st.SearchStrategy,
    ) -> CheckResult:
        """Find an input where pre_A and pre_B disagree."""

        found: list[Disagreement] = []
        tried = [0]

        @given(input_strategy)
        @settings(
            max_examples=self.max_examples_precondition,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
            deadline=None,
        )
        def _test(i: Any) -> None:
            tried[0] += 1
            a_pre = spec_a.check_pre(i)
            b_pre = spec_b.check_pre(i)
            if a_pre != b_pre:
                found.append(
                    classify(
                        "precondition",
                        spec_a_verdict=a_pre,
                        spec_b_verdict=b_pre,
                        input_val=i,
                        output_val=None,
                        spec_a_name=spec_a.name,
                        spec_b_name=spec_b.name,
                    )
                )
                assert False  # trigger Hypothesis shrinking

        try:
            _test()
        except AssertionError:
            pass
        return CheckResult(
            check="precondition",
            disagreement=found[-1] if found else None,
            examples_tried=tried[0],
        )

    def _check_soundness(
        self,
        spec_a: Spec,
        spec_b: Spec,
        impl: Callable[[Any], Any],
        input_strategy: st.SearchStrategy,
    ) -> CheckResult:
        """Find an input where the impl's output is accepted by one spec, rejected by the other."""

        found: list[Disagreement] = []
        tried = [0]

        @given(input_strategy)
        @settings(
            max_examples=self.max_examples_soundness,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
            deadline=None,
        )
        def _test(i: Any) -> None:
            tried[0] += 1
            if not (spec_a.check_pre(i) and spec_b.check_pre(i)):
                return
            try:
                o = impl(i)
            except Exception:
                return
            crashed: Optional[str] = None
            try:
                a_post = spec_a.check_post(i, o)
            except Exception:
                a_post = False
                crashed = spec_a.name
            try:
                b_post = spec_b.check_post(i, o)
            except Exception:
                b_post = False
                if crashed is None:
                    crashed = spec_b.name
            if a_post != b_post:
                found.append(
                    classify(
                        "soundness",
                        spec_a_verdict=a_post,
                        spec_b_verdict=b_post,
                        input_val=i,
                        output_val=o,
                        spec_a_name=spec_a.name,
                        spec_b_name=spec_b.name,
                        crashed=crashed,
                    )
                )
                assert False

        try:
            _test()
        except AssertionError:
            pass
        return CheckResult(
            check="soundness",
            disagreement=found[-1] if found else None,
            examples_tried=tried[0],
        )

    def _check_uniqueness(
        self,
        spec_a: Spec,
        spec_b: Spec,
        input_strategy: st.SearchStrategy,
        output_strategy: st.SearchStrategy,
    ) -> CheckResult:
        """Find an input + mutated output accepted by one spec, rejected by the other."""

        found: list[Disagreement] = []
        tried = [0]

        @given(input_strategy, output_strategy)
        @settings(
            max_examples=self.max_examples_uniqueness,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
            deadline=None,
        )
        def _test(i: Any, o_mut: Any) -> None:
            tried[0] += 1
            if not (spec_a.check_pre(i) and spec_b.check_pre(i)):
                return
            crashed: Optional[str] = None
            try:
                a_post = spec_a.check_post(i, o_mut)
            except Exception:
                a_post = False
                crashed = spec_a.name
            try:
                b_post = spec_b.check_post(i, o_mut)
            except Exception:
                b_post = False
                if crashed is None:
                    crashed = spec_b.name
            if a_post != b_post:
                found.append(
                    classify(
                        "uniqueness",
                        spec_a_verdict=a_post,
                        spec_b_verdict=b_post,
                        input_val=i,
                        output_val=o_mut,
                        spec_a_name=spec_a.name,
                        spec_b_name=spec_b.name,
                        crashed=crashed,
                    )
                )
                assert False

        try:
            _test()
        except AssertionError:
            pass
        return CheckResult(
            check="uniqueness",
            disagreement=found[-1] if found else None,
            examples_tried=tried[0],
        )
