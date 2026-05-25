"""Tests for the FixtureProvider."""

from __future__ import annotations

from pathlib import Path

import pytest

from diffspec.llm import FixtureProvider, _strip_code_fences


REPO = Path(__file__).resolve().parents[1]


def test_fixture_provider_finds_existing_task():
    p = FixtureProvider(REPO / "benchmark")
    r = p.get("sort", "claude")
    assert r.model == "claude"
    assert "def pre" in r.source
    assert "def post" in r.source


def test_fixture_provider_missing_task_raises():
    p = FixtureProvider(REPO / "benchmark")
    with pytest.raises(FileNotFoundError):
        p.get("does_not_exist", "claude")


def test_strip_code_fences():
    fenced = "```python\ndef pre(i): return True\n```"
    assert _strip_code_fences(fenced) == "def pre(i): return True"

    plain = "def pre(i): return True"
    assert _strip_code_fences(plain) == plain
