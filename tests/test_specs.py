"""Tests for the spec loader."""

from __future__ import annotations

import pytest

from diffspec.specs import (
    Spec,
    SpecLoadError,
    load_spec_from_source,
)


GOOD_SOURCE = """
def pre(i):
    return isinstance(i, list)
def post(i, o):
    return sorted(i) == o
"""


def test_loads_a_well_formed_spec():
    s = load_spec_from_source("test", GOOD_SOURCE)
    assert isinstance(s, Spec)
    assert s.check_pre([3, 1, 2])
    assert s.check_post([3, 1, 2], [1, 2, 3])
    assert not s.check_post([3, 1, 2], [1, 2])


def test_rejects_source_missing_pre_or_post():
    with pytest.raises(SpecLoadError):
        load_spec_from_source("x", "def pre(i): return True")
    with pytest.raises(SpecLoadError):
        load_spec_from_source("x", "def post(i, o): return True")


def test_rejects_disallowed_imports():
    with pytest.raises(SpecLoadError):
        load_spec_from_source(
            "x",
            "import os\ndef pre(i): return True\ndef post(i,o): return True",
        )


def test_allows_stdlib_imports():
    src = """
import math
def pre(i):
    return isinstance(i, float)
def post(i, o):
    return o == math.floor(i)
"""
    s = load_spec_from_source("x", src)
    assert s.check_post(3.7, 3)


def test_syntax_error_is_surfaced():
    with pytest.raises(SpecLoadError):
        load_spec_from_source("x", "def pre(i)\n    return True")


def test_pre_exception_is_treated_as_false():
    src = """
def pre(i):
    return 1 / 0
def post(i, o):
    return True
"""
    s = load_spec_from_source("x", src)
    assert s.check_pre("anything") is False
