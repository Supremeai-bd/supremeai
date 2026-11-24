"""Request models for the standalone scraper/browser service (``browser/main.py``).

Deliberately *not* called ``schemas``: ``browser/`` is prepended to ``sys.path``
by ``browser/main.py`` and ``browser/tests/conftest.py``, so a module named
``schemas`` here silently shadows the top-level ``schemas`` package
(``core/schemas``) for the whole process.

Audit item ③ / ⑳ fix (2026-11-24): ``RecipeRequest.steps`` used to be
``list = []`` — an untyped, mutable-default field. Two concrete failures
followed from that:

1. Any JSON shape reached ``BrowserAgent.execute_recipe``, which reads
   ``step.get(...)`` per item. ``{"steps": ["click"]}`` therefore raised
   ``AttributeError`` *inside* the Playwright loop (after the browser was
   launched) instead of being rejected as a 422 at intake.
2. ``[]`` as a class default is the classic shared-mutable-default trap.

The models live in this dependency-free leaf module so they can be imported and
tested without booting the relay app (``browser/main.py`` constructs the scraper
engine at import time).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Actions the recipe interpreter (``BrowserAgent.execute_recipe``) implements.
#: Anything else is rejected at intake instead of being silently skipped.
RECIPE_ACTIONS: tuple[str, ...] = ("navigate", "click", "type", "wait", "extract")

#: Hard cap on steps per recipe — an unbounded list means an unbounded browser
#: session on a shared host.
MAX_RECIPE_STEPS = 100


class ScrapeRequest(BaseModel):
    """``POST /scrape`` body."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    extraction_prompt: str | None = Field(default=None, max_length=20_000)


class BrowseRequest(BaseModel):
    """``POST /browse`` body (re-exported from the engine when available)."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    action: str | None = Field(default=None, max_length=64)
    selector: str | None = Field(default=None, max_length=512)
    text: str | None = Field(default=None, max_length=20_000)
    wait_for: int | float | None = None


class RecipeStep(BaseModel):
    """One recipe step — typed and bounded (see module docstring)."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["navigate", "click", "type", "wait", "extract"]
    selector: str | None = Field(default=None, max_length=512)
    value: str | None = Field(default=None, max_length=20_000)
    url: str | None = Field(default=None, max_length=2048)
    #: ``extract`` only: ``"list"`` returns every match, ``"text"`` the first.
    type: Literal["list", "text"] | None = None


class RecipeRequest(BaseModel):
    """``POST /recipe`` body."""

    model_config = ConfigDict(extra="forbid")

    steps: list[RecipeStep] = Field(default_factory=list, max_length=MAX_RECIPE_STEPS)
    initial_url: str | None = Field(default=None, max_length=2048)


__all__ = [
    "MAX_RECIPE_STEPS",
    "RECIPE_ACTIONS",
    "BrowseRequest",
    "RecipeRequest",
    "RecipeStep",
    "ScrapeRequest",
]
