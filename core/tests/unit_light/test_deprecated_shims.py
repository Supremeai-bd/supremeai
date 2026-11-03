"""Tests for the deprecated module shims that delegate to their canonical replacements.

Each shim exposes ``__getattr__`` / ``__dir__`` that emit a DeprecationWarning on
first access and forward attribute lookups to the new module path. This single
parametrized suite exercises the remaining ``core`` shim so the shim module is not
left at 0% coverage. (Batches 1-4 archived all other shims; only the
644-importer ``core.logging_config`` bridge remains, own batch pending.)
"""

import importlib
import types
from unittest.mock import patch

import pytest

# (module import path, an attribute name we access to trigger delegation)
_SHIMS = [
    ("core.logging_config", "SomeExport"),
]


def _make_fake_module(attrs):
    fake = types.ModuleType("fake_target")
    fake.__dict__.update(attrs)
    return fake


@pytest.mark.parametrize("module_path,attr", _SHIMS)
def test_shim_delegates_attribute(module_path, attr):
    mod = importlib.import_module(module_path)
    fake = _make_fake_module({attr: 123})
    with patch("importlib.import_module", return_value=fake):
        assert getattr(mod, attr) == 123


@pytest.mark.parametrize("module_path,attr", _SHIMS)
def test_shim_dir_lists_target(module_path, attr):
    mod = importlib.import_module(module_path)
    fake = _make_fake_module({"A": 1, "B": 2})
    with patch("importlib.import_module", return_value=fake):
        assert "A" in dir(mod)


@pytest.mark.parametrize("module_path,attr", _SHIMS)
def test_shim_warns_once(module_path, attr):
    mod = importlib.import_module(module_path)
    importlib.reload(mod)
    fake = _make_fake_module({attr: 1})
    with (
        patch("importlib.import_module", return_value=fake),
        pytest.warns(DeprecationWarning),
    ):
        _ = getattr(mod, attr)
