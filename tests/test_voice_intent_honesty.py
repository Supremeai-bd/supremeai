"""Voice channel honesty contract (audit items ⑤ / ⑱).

The voice WebSocket has real STT (Groq Whisper → OpenAI → Gemini → HuggingFace)
in front of a **simulated** intent step. Before this guard, ``handle_intent``
answered a "/" command with::

    "Executing system command: /deploy... Authorization confirmed."

Nothing was executed, authorized or even parsed — the sentence was invented. A
client (or a demo audience) reading that frame would reasonably conclude work had
started. This test pins the honesty contract instead:

* ``HANDLE_INTENT_SIMULATED`` is ``True`` and must stay ``True`` until a real
  allowlisted intent router exists;
* every frame ``handle_intent`` emits carries ``simulated: True`` (and the
  terminal frame also ``executed: False``), so the UI cannot render a completed
  action;
* the handler contains no execution primitive (no subprocess / os.system /
  eval / exec / shell=True);
* the canned text no longer claims authorization or execution.

Structural (AST) checks are used on purpose: the module imports the Supabase
client, an ORM model and the security layer at import time, none of which are
needed to assert what the handler is allowed to say.

When the real router lands: delete the canned branches, set
``HANDLE_INTENT_SIMULATED = False``, and replace this file with tests that drive
the actual tool calls.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "api" / "routes" / "websocket_voice.py"

#: Phrases that assert work happened. They must never appear in the module.
FORBIDDEN_CLAIMS = (
    "Executing system command",
    "Authorization confirmed",
)

#: Calls that would mean the handler actually runs something.
EXECUTION_PRIMITIVES = {
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "os.system",
    "os.popen",
    "eval",
    "exec",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {MODULE_PATH.name}")


def test_module_declares_simulation_flag():
    tree = _tree()
    flags = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        for target in [node.targets[0]]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)
    }
    flag = flags.get("HANDLE_INTENT_SIMULATED")
    assert getattr(flag, "value", None) is True, (
        "HANDLE_INTENT_SIMULATED must be True while handle_intent only echoes. "
        "If a real intent router landed, update the flag AND rewrite this test."
    )


def test_no_frame_can_claim_execution():
    """Every ``send_json`` frame from ``handle_intent`` carries ``simulated=True``."""
    handler = _find_function(_tree(), "handle_intent")
    frames: list[dict[str, ast.expr]] = []
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "send_json"):
            continue
        assert len(node.args) == 1 and isinstance(node.args[0], ast.Dict), (
            "handle_intent must send a literal dict so its flags stay auditable"
        )
        assert all(isinstance(key, ast.Constant) for key in node.args[0].keys), (
            "frame keys must be literal strings"
        )
        frames.append(
            {
                key.value: value
                for key, value in zip(node.args[0].keys, node.args[0].values, strict=True)
            }
        )

    assert frames, "handle_intent must stream at least one frame"
    for payload in frames:
        assert "simulated" in payload, f"frame {payload.get('type')!r} lacks a simulated flag"
        simulated = payload["simulated"]
        assert isinstance(simulated, ast.Constant) and simulated.value is True, (
            "simulated must be the literal True — a client cannot be trusted to default it"
        )
        assert "surface" in payload, "frames must name the answering surface"


def test_terminal_frame_declares_not_executed():
    handler = _find_function(_tree(), "handle_intent")
    found = False
    for node in ast.walk(handler):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "send_json"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            keys = {
                k.value: v
                for k, v in zip(node.args[0].keys, node.args[0].values, strict=True)
                if isinstance(k, ast.Constant)
            }
            type_val = keys.get("type")
            if isinstance(type_val, ast.Constant) and type_val.value == "response_complete":
                executed = keys.get("executed")
                assert isinstance(executed, ast.Constant) and executed.value is False, (
                    "voice terminal frame must report executed=False"
                )
                found = True
    assert found, "handle_intent must send a response_complete frame"


def test_handler_has_no_execution_primitive():
    handler = _find_function(_tree(), "handle_intent")
    called: list[str] = []
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.append(func.id)
            elif isinstance(func, ast.Attribute):
                prefix = ""
                if isinstance(func.value, ast.Name):
                    prefix = f"{func.value.id}."
                elif isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
                    prefix = f"{func.value.value.id}.{func.value.attr}."
                called.append(f"{prefix}{func.attr}")
    offenders = sorted(set(called) & EXECUTION_PRIMITIVES)
    assert not offenders, f"handle_intent must not execute anything, found {offenders}"


def test_no_forbidden_claims_in_module():
    """No *string* the module can emit may assert execution.

    Only string literals are inspected (comments/docs may quote the old wording
    while explaining the fix).
    """
    literals = [
        node.value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    for phrase in FORBIDDEN_CLAIMS:
        offenders = [literal for literal in literals if phrase in literal]
        assert not offenders, (
            f"{phrase!r} asserts work that does not happen — say plainly that "
            f"nothing was executed (found in {offenders!r})"
        )


def test_command_frames_are_labelled_unavailable():
    """A '/' transcript must be labelled as an unhandled command, not executed."""
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'intent = "command_unavailable"' in source
    assert 'intent = "chat_unavailable"' in source
