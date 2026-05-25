"""DiffSpec-PBT — differential property-based validation of LLM-generated specs."""

from diffspec.specs import Spec, load_spec_from_source, load_spec_from_path
from diffspec.classify import DisagreementType, Disagreement
from diffspec.differ import Differ, CheckResult
from diffspec.report import Report, summarize
from diffspec.llm import (
    SpecProvider,
    FixtureProvider,
    LiveProvider,
    LLMResponse,
)

__version__ = "0.1.0"

__all__ = [
    "Spec",
    "load_spec_from_source",
    "load_spec_from_path",
    "DisagreementType",
    "Disagreement",
    "Differ",
    "CheckResult",
    "Report",
    "summarize",
    "SpecProvider",
    "FixtureProvider",
    "LiveProvider",
    "LLMResponse",
]
