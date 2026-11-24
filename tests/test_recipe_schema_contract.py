"""Recipe / scrape request schema contract (audit item ③).

``RecipeRequest.steps`` used to be an untyped ``list = []``:

* a mutable class default shared between requests;
* no shape enforcement, so ``{"steps": ["click"]}`` reached
  ``BrowserAgent.execute_recipe`` and raised ``AttributeError: 'str' object has
  no attribute 'get'`` **after** Playwright had already been launched;
* no bound, so a caller could queue an arbitrarily long browser session.

The schema now lives in ``browser/schemas.py`` (a dependency-free leaf module) so
it can be tested without booting the relay app, which constructs the scraper
engine at import time.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from browser.schemas import (
    MAX_RECIPE_STEPS,
    RECIPE_ACTIONS,
    RecipeRequest,
    RecipeStep,
    ScrapeRequest,
)


def test_default_steps_are_not_shared_between_instances():
    first, second = RecipeRequest(), RecipeRequest()
    assert first.steps == [] and second.steps == []
    first.steps.append(RecipeStep(action="extract"))
    assert second.steps == [], "mutable default leaked between requests"


def test_every_executed_action_is_accepted():
    for action in RECIPE_ACTIONS:
        step = RecipeStep(action=action)
        assert step.action == action


def test_unknown_action_is_rejected_at_intake():
    with pytest.raises(ValidationError):
        RecipeStep(action="rm -rf /")


def test_non_object_step_is_rejected_at_intake():
    """The exact payload that used to explode inside the browser loop."""
    with pytest.raises(ValidationError):
        RecipeRequest(steps=["click"])


def test_extra_keys_are_rejected():
    with pytest.raises(ValidationError):
        RecipeStep(action="click", selector="#a", script="alert(1)")


def test_step_count_is_bounded():
    step = {"action": "click", "selector": "#a"}
    RecipeRequest(steps=[step] * MAX_RECIPE_STEPS)  # at the limit: fine
    with pytest.raises(ValidationError):
        RecipeRequest(steps=[step] * (MAX_RECIPE_STEPS + 1))


def test_long_selectors_and_values_are_bounded():
    with pytest.raises(ValidationError):
        RecipeStep(action="click", selector="x" * 513)
    with pytest.raises(ValidationError):
        RecipeStep(action="type", selector="#a", value="x" * 20_001)


def test_dump_matches_the_interpreter_contract():
    """``execute_recipe`` reads ``step.get(...)`` — dicts with no ``None`` noise."""
    request = RecipeRequest(
        steps=[{"action": "click", "selector": "#login"}],
        initial_url="https://example.com",
    )
    dumped = [step.model_dump(exclude_none=True) for step in request.steps]
    assert dumped == [{"action": "click", "selector": "#login"}]
    assert request.initial_url == "https://example.com"


def test_scrape_request_requires_url():
    with pytest.raises(ValidationError):
        ScrapeRequest(url="")
    with pytest.raises(ValidationError):
        ScrapeRequest(url="https://example.com", unexpected="x")
