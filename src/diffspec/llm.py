"""Pluggable LLM provider.

Two implementations:

* :class:`FixtureProvider` reads pre-recorded spec source files from
  ``benchmark/<task>/fixtures/<model>.py``. Default mode. Deterministic,
  reproducible, no API keys.

* :class:`LiveProvider` calls NVIDIA NIM at runtime using the
  OpenAI-compatible endpoint at ``https://integrate.api.nvidia.com/v1``.
  Default models are an open Qwen coder model and Meta Llama 3.3 70B,
  both hosted on NIM. Responses are cached into ``fixtures/`` so a
  subsequent fixture-mode run reproduces the same eval.

The differ never sees the LLM directly; it only sees the spec source
returned by the provider.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Default NIM endpoint and model IDs. Override with environment variables
# DIFFSPEC_NIM_BASE_URL, DIFFSPEC_MODEL_QWEN, DIFFSPEC_MODEL_LLAMA if you
# want to swap.
NIM_BASE_URL_DEFAULT = "https://integrate.api.nvidia.com/v1"
QWEN_DEFAULT = "qwen/qwen3-coder-480b-a35b-instruct"
LLAMA_DEFAULT = "meta/llama-3.3-70b-instruct"


SPEC_PROMPT_TEMPLATE = """\
You are a formal-methods expert. Given a natural-language requirement,
emit a formal specification as two Python functions named exactly `pre`
and `post`.

  * `pre(i)` returns True if and only if `i` is a valid input.
  * `post(i, o)` returns True if and only if `o` is a correct output for
    valid input `i`.

Output ONLY executable Python source code defining `pre` and `post` at
the top level. No markdown fences, no commentary, no imports outside
the Python standard library.

Requirement:
{requirement}
"""


@dataclass(frozen=True)
class LLMResponse:
    """A spec source returned by some provider, tagged with the model name."""

    model: str
    source: str


def load_env(path: str | Path | None = None) -> None:
    """Tiny .env loader so we don't add python-dotenv as a hard dep.

    Walks up from `path` (or the current working directory) until it
    finds a `.env` file, then loads any ``KEY=VALUE`` lines into
    ``os.environ``. Existing environment values win.
    """

    p = Path(path) if path else Path.cwd()
    for parent in [p, *p.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
            return


class SpecProvider(ABC):
    """Abstract spec source."""

    @abstractmethod
    def get(self, task: str, model: str) -> LLMResponse:
        """Return the spec source for (task, model)."""


# ---------------------------------------------------------------------------
# Fixture provider
# ---------------------------------------------------------------------------

class FixtureProvider(SpecProvider):
    """Read spec sources from ``benchmark/<task>/fixtures/<model>.py``."""

    def __init__(self, benchmark_root: str | Path) -> None:
        self.root = Path(benchmark_root)

    def get(self, task: str, model: str) -> LLMResponse:
        task_dir = _find_task_dir(self.root, task)
        fpath = task_dir / "fixtures" / f"{model}.py"
        if not fpath.exists():
            raise FileNotFoundError(f"fixture not found: {fpath}")
        return LLMResponse(model=model, source=fpath.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Live provider (NVIDIA NIM)
# ---------------------------------------------------------------------------

class LiveProvider(SpecProvider):
    """Calls NVIDIA NIM via its OpenAI-compatible endpoint.

    Generated specs are written to ``benchmark/<task>/fixtures/<model>.py``
    so subsequent fixture-mode runs reproduce the same eval.
    """

    def __init__(
        self,
        benchmark_root: str | Path,
        base_url: Optional[str] = None,
        qwen_model: Optional[str] = None,
        llama_model: Optional[str] = None,
    ) -> None:
        load_env(benchmark_root)
        self.root = Path(benchmark_root)
        self.base_url = base_url or os.environ.get(
            "DIFFSPEC_NIM_BASE_URL", NIM_BASE_URL_DEFAULT
        )
        self.qwen_model = qwen_model or os.environ.get("DIFFSPEC_MODEL_QWEN", QWEN_DEFAULT)
        self.llama_model = llama_model or os.environ.get(
            "DIFFSPEC_MODEL_LLAMA", LLAMA_DEFAULT
        )

    def resolve_model(self, alias: str) -> str:
        """Map shorthand ``qwen`` / ``llama`` aliases to full NIM model IDs."""

        a = alias.lower()
        if a in {"qwen", "claude"}:  # 'claude' alias kept for back-compat
            return self.qwen_model
        if a in {"llama", "gpt"}:    # 'gpt' alias kept for back-compat
            return self.llama_model
        return alias  # already a full NIM id

    def get(self, task: str, alias: str) -> LLMResponse:
        task_dir = _find_task_dir(self.root, task)
        req_path = task_dir / "requirement.md"
        requirement = req_path.read_text(encoding="utf-8")

        fixture_path = task_dir / "fixtures" / f"{alias}.py"

        prompt = SPEC_PROMPT_TEMPLATE.format(requirement=requirement)
        nim_model = self.resolve_model(alias)
        source = self._call_nim(nim_model, prompt)

        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# Auto-generated by DiffSpec-PBT LiveProvider\n"
            f"# nim_model: {nim_model}\n"
            f"# task: {task_dir.name}\n"
        )
        fixture_path.write_text(header + source.strip() + "\n", encoding="utf-8")
        return LLMResponse(model=alias, source=source)

    def _call_nim(self, model: str, prompt: str) -> str:
        key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NIM_API_KEY")
        if not key:
            raise RuntimeError(
                "NVIDIA_API_KEY not set; live mode unavailable. "
                "Put NVIDIA_API_KEY=... into .env or export it."
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "live mode needs `pip install openai`"
            ) from exc

        client = OpenAI(api_key=key, base_url=self.base_url)
        rsp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
        )
        return _strip_code_fences(rsp.choices[0].message.content or "")


# ---------------------------------------------------------------------------

def _find_task_dir(root: Path, task: str) -> Path:
    """Find ``root/<NN>_<name>`` matching `task` (substring or exact)."""

    candidates = sorted(p for p in root.iterdir() if p.is_dir() and task in p.name)
    if not candidates:
        # Try without leading numeric prefix
        candidates = sorted(
            p for p in root.iterdir()
            if p.is_dir() and p.name.split("_", 1)[-1] == task
        )
    if not candidates:
        raise FileNotFoundError(f"no benchmark dir matching {task!r} under {root}")
    return candidates[0]


def _strip_code_fences(text: str) -> str:
    """Strip surrounding triple-backtick code fences if present."""

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1])
    return text
