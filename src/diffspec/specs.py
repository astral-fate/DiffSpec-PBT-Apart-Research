"""Spec dataclass and exec-safe loader.

A spec is a Python source string that defines two functions:

    def pre(i): ...
    def post(i, o): ...

We compile and execute the source inside a fresh namespace, then wrap
the resulting callables in a :class:`Spec`. The loader does a quick AST
sanity check to reject anything that looks like an import outside the
standard library or an attribute access into ``__class__``-style escape
hatches.

This is *not* a security boundary against malicious specs (we run trusted
LLM output in a development context, not user input). It is a guard
against accidental noise: top-level prints, dangling expressions,
imports of compute-heavy libraries that would slow the differ down.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


_ALLOWED_IMPORTS = {
    "math",
    "re",
    "string",
    "itertools",
    "functools",
    "collections",
    "typing",
}


class SpecLoadError(ValueError):
    """Raised when a spec source string is not loadable."""


@dataclass(frozen=True)
class Spec:
    """A formal specification expressed as Python pre/post functions."""

    name: str
    pre: Callable[[Any], bool]
    post: Callable[[Any, Any], bool]
    source: str
    origin: str = ""

    def check_pre(self, i: Any) -> bool:
        try:
            return bool(self.pre(i))
        except Exception:
            return False

    def check_post(self, i: Any, o: Any) -> bool:
        try:
            return bool(self.post(i, o))
        except Exception:
            return False


def _ast_sanity(source: str) -> None:
    """Quick AST sanity pass: only allow safe imports; require `pre` and `post`."""

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SpecLoadError(f"syntax error: {exc.msg} at line {exc.lineno}") from exc

    defined = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [n.name.split(".")[0] for n in node.names]
            else:
                mods = [(node.module or "").split(".")[0]]
            for m in mods:
                if m and m not in _ALLOWED_IMPORTS:
                    raise SpecLoadError(
                        f"disallowed import {m!r}; allowed: {sorted(_ALLOWED_IMPORTS)}"
                    )
        elif isinstance(node, ast.FunctionDef):
            defined.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            # Top-level constants are fine.
            continue
        # Other top-level statements (Expr, etc.) are tolerated but ignored.

    missing = {"pre", "post"} - defined
    if missing:
        raise SpecLoadError(
            f"spec source must define functions: missing {sorted(missing)}"
        )


def load_spec_from_source(name: str, source: str, origin: str = "") -> Spec:
    """Compile a spec source string and return a :class:`Spec` instance."""

    _ast_sanity(source)
    namespace: dict[str, Any] = {}
    try:
        exec(compile(source, origin or f"<spec {name}>", "exec"), namespace)
    except Exception as exc:  # narrow on purpose - exec-time errors
        raise SpecLoadError(f"spec exec failed: {exc!r}") from exc

    pre = namespace.get("pre")
    post = namespace.get("post")
    if not callable(pre) or not callable(post):
        raise SpecLoadError("spec must export callable `pre` and `post`")

    return Spec(name=name, pre=pre, post=post, source=source, origin=origin)


def load_spec_from_path(name: str, path: str | Path) -> Spec:
    p = Path(path)
    return load_spec_from_source(name, p.read_text(encoding="utf-8"), origin=str(p))
