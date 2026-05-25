"""Tests for the Differ end-to-end on synthetic spec pairs."""

from __future__ import annotations

from hypothesis import strategies as st

from diffspec.differ import Differ
from diffspec.classify import DisagreementType
from diffspec.specs import load_spec_from_source


WEAK = """
def pre(i):
    return isinstance(i, list)
def post(i, o):
    # Only checks non-decreasing -- missing permutation invariant.
    if not isinstance(o, list):
        return False
    for k in range(len(o) - 1):
        if o[k] > o[k+1]:
            return False
    return True
"""

STRONG = """
def pre(i):
    return isinstance(i, list)
def post(i, o):
    return isinstance(o, list) and sorted(i) == o
"""


def test_differ_finds_uniqueness_disagreement():
    weak = load_spec_from_source("weak", WEAK)
    strong = load_spec_from_source("strong", STRONG)
    d = Differ()
    results = d.diff(
        weak, strong,
        impl=sorted,
        input_strategy=st.lists(st.integers(min_value=-5, max_value=5), max_size=5),
        output_strategy=st.lists(st.integers(min_value=-5, max_value=5), max_size=5),
    )
    by_check = {r.check: r for r in results}
    # The two specs agree on real outputs but disagree on mutated outputs.
    assert by_check["soundness"].disagreement is None
    assert by_check["uniqueness"].disagreement is not None
    assert by_check["uniqueness"].disagreement.type in {
        DisagreementType.UNDERSPEC,
        DisagreementType.EDGE_DRIFT,
    }


def test_differ_finds_precondition_mismatch():
    src_a = """
def pre(i):
    return isinstance(i, list) and len(i) > 0
def post(i, o):
    return o == max(i)
"""
    src_b = """
def pre(i):
    return isinstance(i, list)
def post(i, o):
    if not i:
        return o is None
    return o == max(i)
"""
    a = load_spec_from_source("a", src_a)
    b = load_spec_from_source("b", src_b)

    def impl(i):
        return None if not i else max(i)

    d = Differ()
    results = d.diff(
        a, b, impl=impl,
        input_strategy=st.lists(st.integers(min_value=-5, max_value=5), max_size=3),
    )
    by_check = {r.check: r for r in results}
    assert by_check["precondition"].disagreement is not None
    assert by_check["precondition"].disagreement.type == DisagreementType.PRECOND_MISMATCH


def test_differ_returns_no_disagreement_for_equivalent_specs():
    a = load_spec_from_source("a", STRONG)
    b = load_spec_from_source("b", STRONG)
    d = Differ()
    results = d.diff(
        a, b, impl=sorted,
        input_strategy=st.lists(st.integers(min_value=-5, max_value=5), max_size=4),
        output_strategy=st.lists(st.integers(min_value=-5, max_value=5), max_size=4),
    )
    assert all(r.disagreement is None for r in results)
