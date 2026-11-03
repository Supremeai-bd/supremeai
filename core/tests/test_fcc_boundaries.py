"""FCC boundary enforcement — architecture tests for the circle federation.

The Federated Capability Circle Architecture forbids direct
module-to-module dependency. These tests enforce the rule mechanically so
it cannot erode over time:

1. A circle center must NEVER import another circle center.
2. A circle center must NOT touch the legacy flat registry or the
   governance core directly — cross-circle traffic goes through the
   envelope the GovernanceCore routes.
3. The GovernanceCore stays SMALL: it must not import domain modules
   (brain/memory/api/storage/…) — only circle contracts/envelopes, the
   center base class, the event journal, and (inside the singleton
   factory) the federation bootstrap that wires centers in.
"""

import ast
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
CENTERS_DIR = BACKEND_ROOT / "core" / "circles" / "centers"
GOVERNANCE_CORE = BACKEND_ROOT / "core" / "circles" / "governance_core.py"

_CENTER_MODULES = {
    path.stem for path in CENTERS_DIR.glob("*.py") if path.name not in {"__init__.py", "base.py"}
}

_FORBIDDEN_IN_CENTERS_PREFIXES = (
    "core.circles.governance_core",
    "core.circles.registry",
)

_ALLOWED_IN_GOVERNANCE = {
    "__future__",
    "asyncio",
    "threading",
    "time",
    "typing",
    "uuid",
    "collections",
    "dataclasses",
    "datetime",
    "json",
    "pydantic",
    # circle-internal, domain-free modules only:
    "core.circles.contracts",
    "core.circles.envelopes",
    "core.circles.event_journal",
    "core.circles.centers.base",
    # documented exception: the singleton factory wires centers in lazily
    "core.circles.bootstrap",
}


def _absolute_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
    return found


class CenterBoundaryTests(unittest.TestCase):
    def test_centers_exist_for_every_circle(self) -> None:
        from core.circles.centers import center_types_by_circle
        from core.circles.contracts import CircleName

        wired = center_types_by_circle()
        for circle in CircleName:
            self.assertIn(circle, wired, f"missing circle center for {circle.value}")

    def test_no_center_imports_another_center(self) -> None:
        for module in sorted(_CENTER_MODULES):
            path = CENTERS_DIR / f"{module}.py"
            for imported in _absolute_imports(path):
                target = imported.rsplit(".", 1)[-1]
                if imported.startswith("core.circles.centers") and target in (
                    _CENTER_MODULES - {module}
                ):
                    self.fail(
                        f"FCC violation: '{module}' imports another circle center "
                        f"'{imported}'. Cross-circle calls must go through the "
                        "GovernanceCore envelope."
                    )

    def test_centers_do_not_touch_governance_core_or_legacy_registry(self) -> None:
        for module in sorted(_CENTER_MODULES):
            path = CENTERS_DIR / f"{module}.py"
            for imported in _absolute_imports(path):
                for forbidden in _FORBIDDEN_IN_CENTERS_PREFIXES:
                    if imported == forbidden or imported.startswith(f"{forbidden}."):
                        self.fail(
                            f"FCC violation: '{module}' imports '{imported}'. "
                            "Centers receive routing only via the federation."
                        )

    def test_centers_local_concerns_present(self) -> None:
        from core.circles.centers.base import CircleCenter

        for hook in ("local_permission", "resolve_adapter", "health", "handle"):
            self.assertTrue(hasattr(CircleCenter, hook), f"missing local concern: {hook}")


class GovernanceCoreBoundaryTests(unittest.TestCase):
    def test_governance_core_has_no_domain_imports(self) -> None:
        for imported in _absolute_imports(GOVERNANCE_CORE):
            root = imported.split(".")[0]
            if imported in _ALLOWED_IN_GOVERNANCE:
                continue
            if root in {"core", "api", "brain", "memory", "storage", "models", "workers", "agents"}:
                self.fail(
                    f"FCC violation: governance_core imports '{imported}'. The Global "
                    "Governance Core must stay small — domain logic belongs to the "
                    "circle centers."
                )

    def test_envelope_is_the_only_wire_contract(self) -> None:
        from core.circles.envelopes import ExecutionEnvelope, ResultEnvelope

        request = ExecutionEnvelope.model_fields.keys()
        self.assertEqual(
            set(request),
            {
                "execution_id",
                "circle",
                "capability",
                "tenant_id",
                "actor_id",
                "correlation_id",
                "payload",
                "policy",
                "deadline_ms",
            },
        )
        self.assertEqual(
            set(ResultEnvelope.model_fields.keys()),
            {"execution_id", "status", "circle", "data", "events", "error"},
        )

    def test_federation_advertises_registered_capabilities_only(self) -> None:
        from core.circles.bootstrap import (  # Issue #2476: singleton moved to composition root
            get_governance_core,
            reset_governance_core,
        )

        reset_governance_core()
        try:
            core = get_governance_core()
            manifests = {manifest.name: manifest for manifest in core.manifests()}
            for center in core.centers():
                manifest = manifests[center.circle]
                manifest_caps = {ref.name for ref in manifest.capabilities}
                local_caps = set(center.capabilities())
                self.assertEqual(
                    manifest_caps,
                    local_caps,
                    f"{center.circle.value} center advertises capabilities it "
                    "does not serve locally",
                )
        finally:
            reset_governance_core()


if __name__ == "__main__":
    unittest.main()
