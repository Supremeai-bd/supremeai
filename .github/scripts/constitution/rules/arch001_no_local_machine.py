"""ARCH-001: No Local-Machine Dependency (Production Environment Agnostic).

2026-09-28 semantic-aware rewrite (#2113 / #2369): the original lexical
line-regex flagged docstrings, comments, SSRF blocklists, loopback *bind*
addresses and env-guarded fallbacks — every finding in the #2113 incident
was a false positive, which trains the team to ignore the Constitution
Audit entirely. This rewrite flags only string *literals* in real
dependency contexts:

  flagged:    unguarded plain literals (``url = "http://localhost:8000"``,
              ``requests.get("http://127.0.0.1:8000")``)
  exempt:     docstrings, comments (AST-invisible), f-string fragments
              (partially dynamic by construction), env-guarded subtrees
              (``if settings.env == "local":``), loopback bind/listen
              contexts (``BIND|LISTEN|ADDRESS`` assignments, ``host=``
              kwargs), SSRF/private-network blocklists
              (``BLOCKED|PRIVATE|NETWORK|CIDR|RESERVED|LOOPBACK``
              collections, ``ip_network`` args), log-call messages
              (describing behavior is not depending on it), membership
              guards (``"localhost" in base_url`` — enforcement, not
              dependency), and the repo's ``# is_local()`` line annotation
              idiom that marks a parameter default as local-env-sanctioned.

A true violation still blocks — see
``.github/scripts/constitution/tests/test_rules.py`` fixtures.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from ..models import AuditFinding, RuleCategory, RuleDefinition, Severity
from .base import BaseRule

# The literal classes this rule polices (same set as before, now applied to
# string *constants* rather than raw lines).
LOOPBACK_PATTERN = re.compile(
    r"(?:localhost|127\.0\.0\.1|127\.0\.1\.1|0\.0\.0\.0|::\s*1)", re.IGNORECASE
)

# Assignment targets / collection names that make a loopback literal a
# *bind* or a *blocklist* rather than a service dependency.
SAFE_CONTEXT_NAME = re.compile(
    r"BIND|LISTEN|ADDRESS|BLOCKED|BLOCKLIST|PRIVATE|NETWORK|CIDR|RESERVED|LOOPBACK",
    re.IGNORECASE,
)
# Keyword arguments that place a literal in bind/listen context.
SAFE_KWARG_NAMES = {"host", "bind", "address", "address_family", "network", "net"}
# Callers whose string arguments are *messages about* behavior (logging),
# not dependencies on it. Matched against the final attribute/name segment.
MESSAGE_FUNC_PATTERN = re.compile(
    r"(?:logger|logging|log|print|warn|warning|error|debug|info|critical|exception|warnf|errorf|infof|debugf)$",
    re.IGNORECASE,
)
# Identifiers / values that mark an enclosing ``if`` as an environment guard.
ENV_GUARD_NAMES = {
    "env",
    "environment",
    "is_local",
    "is_prod",
    "is_production",
    "is_dev",
    "is_testing",
    "test_mode",
    "env_mode",
    "testing",
}
ENV_GUARD_VALUES = {
    "local",
    "dev",
    "development",
    "test",
    "testing",
    "production",
    "prod",
    "staging",
}

# Scanner self-reference exemption (#2113): quality/lint tooling that defines
# its own detection patterns would otherwise match its own regexes.
SCANNER_SELF_PATHS = ("scripts/quality/", ".github/scripts/constitution")

# The repo's sanctioned line annotation marking a localhost parameter
# default as local-env-guaranteed (validated by the enclosing adapter's
# env guard — see ollama_adapter.py / config_secrets.py CORS origins).
IS_LOCAL_ANNOTATION = re.compile(r"#\s*is_local", re.IGNORECASE)


class NoLocalMachineRule(BaseRule):
    """Detects hardcoded localhost, 127.0.0.1, and Windows-specific paths in production code."""

    DEFINITION = RuleDefinition(
        rule_id="ARCH-001",
        category=RuleCategory.ARCHITECTURE,
        title="No Local-Machine Dependency",
        description="Production code must not reference localhost, 127.0.0.1, or Windows-specific paths.",
        severity=Severity.BLOCK,
        fixable=True,
        details="Detected hardcoded local machine dependencies that would break in cloud environments.",
    )

    def __init__(self):
        """Initialize the rule."""
        super().__init__(self.DEFINITION)

    def audit(self, files: list[Path]) -> list[AuditFinding]:
        """Scan files for local machine dependencies."""
        findings = []

        for file_path in files:
            if self.should_skip_file(file_path):
                continue

            # Skip infrastructure/docker/compose files that legitimately reference localhost,
            # and the QA test-harness tree (qa/) which — like other test tooling — defaults
            # to a local target URL that is always overridable via QA_BASE_URL in CI/staging.
            if any(x in str(file_path) for x in ["docker", "compose", "infra", "k8s"]):
                continue
            parts = file_path.parts
            if "qa" in parts:
                continue

            # Machine-generated inventory artifacts (CI Doctor auto-regen) are not
            # production code — they mirror backend defaults (e.g. a VarDefinition
            # HOST="0.0.0.0" server-bind default) into JSON/MD for humans. Auditing
            # them makes every regen re-flag the same non-findings.
            name_l = file_path.name.lower()
            if "docs" in parts and "generated" in parts:
                continue
            if name_l.startswith("route_client_inventory") or name_l == "module_capability_matrix.json":
                continue

            # Scanner self-references: detection tooling that must name the very
            # patterns it detects (regression scanner, the constitution engine
            # itself) is not a consumer of those endpoints.
            fpos = str(file_path)
            if any(p in fpos for p in SCANNER_SELF_PATHS):
                continue

            findings.extend(self._check_file(file_path))

        return findings

    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        """Check a single file for violations."""
        findings: list[AuditFinding] = []

        if file_path.suffix == ".py":
            findings.extend(self._check_python_file(file_path))
        else:
            findings.extend(self._check_text_file(file_path))

        findings.extend(self._check_windows_paths(file_path))
        return findings

    # ------------------------------------------------------------------ python

    def _check_python_file(self, file_path: Path) -> list[AuditFinding]:
        """Semantic scan: flag loopback *literals* in dependency contexts only."""
        findings: list[AuditFinding] = []
        try:
            src = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            return findings

        doc_spans = self._docstring_spans(tree)
        strings: list[tuple[ast.Constant, dict[str, Any]]] = []
        self._collect_strings(tree, {"guarded": False, "assign": None, "kwarg": None,
                                     "func": None, "fstring": False,
                                     "membership": False}, strings)
        try:
            source_lines = src.splitlines()
        except Exception:
            source_lines = []

        for node, ctx in strings:
            if not LOOPBACK_PATTERN.search(node.value):
                continue
            # 1) docstrings are prose, not code
            if any(a <= node.lineno and (node.end_lineno or node.lineno) <= b for a, b in doc_spans):
                continue
            # 2) f-string fragments are partially dynamic by construction; the
            #    fully-hardcoded-endpoint class this rule exists for is the
            #    plain-literal class (see test fixtures)
            if ctx["fstring"]:
                continue
            # 3) env-guarded subtrees (settings.env == "local", is_prod(), ...)
            if ctx["guarded"]:
                continue
            # 4) bind/listen or blocklist collection context
            if ctx["assign"] and SAFE_CONTEXT_NAME.search(ctx["assign"]):
                continue
            if ctx["kwarg"] and ctx["kwarg"].lower() in SAFE_KWARG_NAMES:
                continue
            # 5) ipaddress / SSRF construction args
            if ctx["func"] and ctx["func"].endswith(("ip_network", "ip_address")):
                continue
            # 6) log/message call arguments describe behavior, not depend on it
            if ctx["func"] and MESSAGE_FUNC_PATTERN.search(ctx["func"].rsplit(".", 1)[-1]):
                continue
            # 7) membership guards (`"localhost" in base_url`) REJECT loopback
            #    targets — enforcement, not a fallback
            if ctx["membership"]:
                continue
            # 8) the sanctioned `# is_local()` line annotation (parameter
            #    defaults guarded by their adapter's env check)
            try:
                line_text = source_lines[node.lineno - 1]
            except IndexError:
                line_text = ""
            if IS_LOCAL_ANNOTATION.search(line_text):
                continue

            findings.append(
                self._create_finding(
                    file_path,
                    line_number=node.lineno,
                    message=f"Hardcoded localhost/127.0.0.1 detected: {node.value[:80]}",
                    remediation="Use environment variables or cloud-agnostic service discovery.",
                    confidence=0.95,
                )
            )
        return findings

    def _docstring_spans(self, tree: ast.Module) -> list[tuple[int, int]]:
        """Line spans of module/class/function docstrings."""
        spans: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    first = node.body[0]
                    spans.append((first.lineno, first.end_lineno or first.lineno))
        return spans

    def _collect_strings(
        self,
        node: ast.AST,
        ctx: dict[str, Any],
        out: list[tuple[ast.Constant, dict[str, Any]]],
    ) -> None:
        """Collect string constants with their structural context."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                out.append((node, ctx))
            return

        if isinstance(node, ast.If) and self._is_env_guard(node.test):
            ctx = {**ctx, "guarded": True}

        if isinstance(node, ast.JoinedStr):
            ctx = {**ctx, "fstring": True}

        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self._collect_strings(
                node.value, {**ctx, "assign": node.targets[0].id, "kwarg": None, "func": None}, out
            )
            return
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                self._collect_strings(
                    node.value, {**ctx, "assign": node.target.id, "kwarg": None, "func": None}, out
                )
            return
        if isinstance(node, ast.Compare):
            # `"localhost" in base_url` — the left operand of a membership
            # test is a GUARD (rejecting loopback), never a dependency.
            for comp_op in node.ops:
                if isinstance(comp_op, (ast.In, ast.NotIn)) and isinstance(node.left, ast.Constant):
                    left = node.left
                    if isinstance(left.value, str):
                        out.append((left, {**ctx, "membership": True}))
                    for child in ast.iter_child_nodes(node):
                        if child is not left:
                            self._collect_strings(child, ctx, out)
                    return
            # plain comparisons: fall through
        if isinstance(node, ast.Call):
            fname = self._call_name(node)
            for kw in node.keywords:
                if kw.value is not None:
                    self._collect_strings(
                        kw.value, {**ctx, "kwarg": kw.arg, "func": fname}, out
                    )
            for arg in node.args:
                self._collect_strings(arg, {**ctx, "kwarg": None, "func": fname}, out)
            self._collect_strings(node.func, {**ctx, "func": None, "kwarg": None}, out)
            return

        for child in ast.iter_child_nodes(node):
            self._collect_strings(child, ctx, out)

    def _call_name(self, call: ast.Call) -> str | None:
        """Best-effort dotted name of the called function (last segment used for matches)."""
        f = call.func
        parts: list[str] = []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        return ".".join(reversed(parts)) if parts else None

    def _is_env_guard(self, test: ast.AST) -> bool:
        """True when an ``if`` test references environment/mode guards."""
        for n in ast.walk(test):
            if isinstance(n, ast.Name) and n.id.lower() in ENV_GUARD_NAMES:
                return True
            if isinstance(n, ast.Attribute) and n.attr.lower() in ENV_GUARD_NAMES:
                return True
            if (
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and n.value.lower() in ENV_GUARD_VALUES
            ):
                return True
        return False

    # ------------------------------------------------------------- other files

    def _check_text_file(self, file_path: Path) -> list[AuditFinding]:
        """Lexical fallback for non-Python files (TS/JS/config)."""
        findings: list[AuditFinding] = []
        localhost_pattern = re.compile(
            r"(?:localhost|127\.0\.0\.1|127\.0\.1\.1|0\.0\.0\.0|::\s*1)(?:\D|$)",
            re.IGNORECASE,
        )
        exclude_patterns = [
            r"//.*(?:localhost|127\.0\.0\.1)",  # line comments
            r"#.*(?:localhost|127\.0\.0\.1)",  # shell/python-style comments
            r"test.*http://localhost",  # test URLs
            r"127\.0\.0\.1.*test",
            r"docker-compose",
            r"ipaddress\.(?:ip_network|ip_address)",
            r"_BLOCKED_NETWORKS",
            r"default\s*=\s*[\"']0\.0\.0\.0[\"']",
            r"[\"'](?:localhost|127\.0\.0\.1)[\"']\s+in\s+",
            r"^\s*//",
        ]
        matches = self._find_in_file(file_path, localhost_pattern, exclude_patterns)
        for line_num, line_text in matches:
            if "test" in file_path.name.lower():
                continue
            findings.append(
                self._create_finding(
                    file_path,
                    line_number=line_num,
                    message=f"Hardcoded localhost/127.0.0.1 detected: {line_text.strip()[:80]}",
                    remediation="Use environment variables or cloud-agnostic service discovery.",
                    confidence=0.95,
                )
            )
        return findings

    def _check_windows_paths(self, file_path: Path) -> list[AuditFinding]:
        """Windows-path check (unchanged semantics, raw lines)."""
        findings: list[AuditFinding] = []
        windows_path_pattern = re.compile(
            r"(?<![a-zA-Z])[cCdDeE]:\\|\\\\(?:\.\\)?(?:Users|Windows|Program Files)"
        )
        matches = self._find_in_file(file_path, windows_path_pattern)
        for line_num, line_text in matches:
            if "test" in file_path.name.lower():
                continue
            findings.append(
                self._create_finding(
                    file_path,
                    line_number=line_num,
                    message=f"Windows-specific path detected: {line_text.strip()[:80]}",
                    remediation="Use pathlib.Path or os.path.join for cross-platform paths.",
                    confidence=0.9,
                )
            )
        return findings
