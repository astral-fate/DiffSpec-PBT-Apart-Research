"""Tests for the disagreement classifier."""

from __future__ import annotations

from diffspec.classify import DisagreementType, classify


def test_soundness_failure_maps_to_overspec():
    d = classify(
        "soundness",
        spec_a_verdict=True,
        spec_b_verdict=False,
        input_val=[1, 2, 3],
        output_val=[1, 2, 3],
        spec_a_name="A",
        spec_b_name="B",
    )
    assert d.type == DisagreementType.OVERSPEC


def test_uniqueness_failure_maps_to_underspec():
    d = classify(
        "uniqueness",
        spec_a_verdict=True,
        spec_b_verdict=False,
        input_val=[1, 2, 3],
        output_val=[42],
        spec_a_name="A",
        spec_b_name="B",
    )
    assert d.type == DisagreementType.UNDERSPEC


def test_precondition_failure_maps_to_precond_mismatch():
    d = classify(
        "precondition",
        spec_a_verdict=True,
        spec_b_verdict=False,
        input_val=([], 5),
        output_val=None,
        spec_a_name="A",
        spec_b_name="B",
    )
    assert d.type == DisagreementType.PRECOND_MISMATCH


def test_edge_input_promotes_soundness_to_edge_drift():
    d = classify(
        "soundness",
        spec_a_verdict=True,
        spec_b_verdict=False,
        input_val=[],
        output_val=[],
        spec_a_name="A",
        spec_b_name="B",
    )
    assert d.type == DisagreementType.EDGE_DRIFT


def test_crash_takes_precedence():
    d = classify(
        "soundness",
        spec_a_verdict=False,
        spec_b_verdict=True,
        input_val=[1],
        output_val=[1],
        spec_a_name="A",
        spec_b_name="B",
        crashed="A",
    )
    assert d.type == DisagreementType.CRASH
