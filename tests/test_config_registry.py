#!/usr/bin/env python3
"""#124 contract tests — canonical configuration registry facade (Phase-3 SSOT).

বাংলা: Phase-3-এর চুক্তি — `core/config_registry.py` শুধুমাত্র SSOT-এর facade,
কোনো ডেটা-কপি নয় (issue-ঘোষিত `core/config/registry.py` পথটি `core/config.py`
Settings মডিউলের namespace-collision-এর কারণে অব্যবহারযোগ্য — boot-smoke-এ
প্রমাণিত); `secrets_registry.yaml` secret-শ্রেণির সব CONFIG_SPECS key কভার করবে;
`.env.example` সবসময় জেনারেটরের সাথে up-to-date থাকবে। এই টেস্টগুলো তিনটি
চুক্তিই মেশিন-চেক করে — facade-এ কেউ ডেটা কপি করলে, registry-তে secret key
বাদ গেলে, বা টেমপ্লেট drift হলে লাউডলি ফেল করবে (Poka-Yoke, #124)।

Verification contract (issue #124, tier 3): pytest tests/test_config_registry.py -v
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core import config_registry as registry  # noqa: E402
from core import config_classification  # noqa: E402
from core import config_validator  # noqa: E402

_GENERATOR = REPO_ROOT / "scripts" / "ci" / "generate_env_example.py"
_SECRETS_REGISTRY = REPO_ROOT / "secrets_registry.yaml"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "supremeai_generate_env_example", _GENERATOR
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _secrets_registry_names() -> set[str]:
    import re

    text = _SECRETS_REGISTRY.read_text(encoding="utf-8")
    return set(re.findall(r"^-\s+name:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", text, re.M))


class TestRegistryFacadeIsSSOTNotCopy(unittest.TestCase):
    """চুক্তি ১: facade = SSOT-এর identity re-export, কপি নয়।"""

    def test_config_specs_identity(self):
        self.assertIs(registry.CONFIG_SPECS, config_classification.CONFIG_SPECS)

    def test_by_name_identity(self):
        self.assertIs(registry.BY_NAME, config_classification.BY_NAME)

    def test_alias_map_identity(self):
        self.assertIs(
            registry.ALIAS_TO_CANONICAL, config_classification.ALIAS_TO_CANONICAL
        )

    def test_config_schema_identity_with_validator(self):
        self.assertIs(registry.CONFIG_SCHEMA, config_validator.CONFIG_SCHEMA)

    def test_schema_is_nonempty_derived_view(self):
        self.assertGreater(len(registry.CONFIG_SCHEMA), 0)
        schema_names = {var.name for var in registry.CONFIG_SCHEMA}
        spec_names = {spec.name for spec in registry.CONFIG_SPECS}
        # বাংলা: derived view SSOT-এর বাইরে নাম বানাতে পারবে না — একমাত্র
        # validator-এর ডিজাইন-অনুমোদিত দুটি পথ ছাড়া: _CONFIG_SCHEMA_OVERRIDES
        # (#1260 follow-up — CONFIG_SPECS-এ অ্যাডপ্ট হওয়া বাকি) এবং
        # legacy-ভ্যালিডেটেড USER_CORS_ORIGINS (validator header-এ ডকুমেন্টেড)।
        overrides = set(getattr(config_validator, "_CONFIG_SCHEMA_OVERRIDES", {}))
        legacy = {"USER_CORS_ORIGINS"}
        unaccounted = sorted(schema_names - spec_names - overrides - legacy)
        self.assertEqual(
            unaccounted,
            [],
            "CONFIG_SCHEMA must not invent names outside CONFIG_SPECS "
            f"(beyond documented overrides/legacy): {unaccounted}",
        )

    def test_helper_resolution_round_trip(self):
        spec = registry.get_config_spec("USER_BACKEND_URL")
        self.assertIsNotNone(spec)
        self.assertEqual(registry.canonical_name(spec.name), spec.name)
        self.assertIn(spec.name, registry.all_config_names())


class TestSecretCoverageContract(unittest.TestCase):
    """চুক্তি ২: secrets_registry.yaml secret-শ্রেণির সব SSOT key কভার করবে।"""

    def test_secret_specs_nonempty(self):
        specs = registry.secret_specs()
        self.assertGreater(len(specs), 0)
        for spec in specs:
            self.assertTrue(spec.is_secret)

    def test_secrets_registry_covers_all_secret_specs(self):
        gaps = registry.secrets_registry_gaps(_secrets_registry_names())
        self.assertEqual(
            gaps,
            (),
            "secrets_registry.yaml must cover every secret-class CONFIG_SPECS "
            f"key — missing: {gaps}. Run scripts/ci/generate_env_example.py",
        )

    def test_generator_append_is_idempotent(self):
        generator = _load_generator()
        added_count, added_names = generator.generate_secrets_registry()
        self.assertEqual((added_count, added_names), (0, []))


class TestTemplateSyncContract(unittest.TestCase):
    """চুক্তি ৩: .env.example জেনারেটরের সাথে up-to-date (drift নিষিদ্ধ)।"""

    def test_env_example_check_passes(self):
        result = subprocess.run(
            [sys.executable, str(_GENERATOR), "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"generate_env_example --check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_every_canonical_key_in_template(self):
        generator = _load_generator()
        by_name, _aliases = generator.load_registry()
        template_keys = set(generator.parse_template(
            (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
        )[1])
        missing = sorted(set(by_name) - template_keys)
        self.assertEqual(
            missing,
            [],
            f"canonical CONFIG_SPECS keys missing from .env.example: {missing}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
