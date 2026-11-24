"""core.agent_tool_policy — who may see and call which governed tool, per tenant.

বাংলা: ``core.tool_loop`` নির্বাহের সময় তিনটি গেট চালায় (flag → রেজিস্ট্রি →
MCP পলিসি)। এই মডিউল তার *আগের* প্রশ্নটার উত্তর দেয় — "এই টেন্যান্টকে কোন
টুলগুলো দেখানো যাবে?" উত্তর তিন স্তরে:

1. **flag** — ``SUPREMEAI_AGENT_TOOLS=true`` না হলে কোনো সারফেস নেই (default OFF)।
2. **per-tenant allowlist** — ``SUPREMEAI_AGENT_TOOL_ALLOWLIST`` (JSON):

   ``{"tenant-a": ["search_database"], "*": ["check_system_health"]}``

   সেট না থাকলে ডিফল্ট = পলিসি-অনুমোদিত (auto-ALLOW) টুলগুলোই — অর্থাৎ
   ঝুঁকি-ভিত্তিক fail-closed; কিছু সেট থাকলে সেটাই একমাত্র সত্য (``"*"`` না
   থাকলে অচেনা টেন্যান্ট = শূন্য টুল)। ভাঙা JSON = শূন্য টুল + দৃশ্যমান ত্রুটি।
3. **MCP পলিসি** — allowlist কেবল *সংকুচিত* করতে পারে, প্রশস্ত করতে নয়:
   ``execute_python_code`` allowlist-এ থাকলেও ঝুঁকি R5 বলে চলে না, আর
   ম্যানিফেস্টে ``requires_approval`` হিসেবে দেখায় (নীরব বাদ নয়)।
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from core.agent_tool_specs import TOOL_SPECS, openai_tool_entry
from core.mcp_policy import evaluate_tool
from core.monitoring.logging_config import logger
from core.tool_loop import agent_tools_enabled, tool_registry

FLAG_ENV = "SUPREMEAI_AGENT_TOOLS"
ALLOWLIST_ENV = "SUPREMEAI_AGENT_TOOL_ALLOWLIST"

#: মানে: allowlist কনফিগার করা হয়নি → পলিসি-অনুমোদিত টুলগুলোই।
_ALLOWLIST_UNSET = "default"


@dataclass
class TenantToolView:
    """এক টেন্যান্টের জন্য টুল-ম্যানিফেস্টের সম্পূর্ণ, সৎ চিত্র।"""

    enabled: bool
    tenant_id: str
    allowlist_source: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    ignored_allowlist_entries: list[str] = field(default_factory=list)
    allowlist_error: str | None = None

    def available_names(self) -> list[str]:
        return [t["function"]["name"] for t in self.tools if t["agent"]["available"]]

    def is_available(self, name: str) -> bool:
        return name in self.available_names()

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "flag": FLAG_ENV,
            "tenantId": self.tenant_id,
            "allowlistSource": self.allowlist_source,
            "allowlistEnv": ALLOWLIST_ENV,
            "allowlistError": self.allowlist_error,
            "ignoredAllowlistEntries": self.ignored_allowlist_entries,
            "tools": self.tools,
        }


def _parse_allowlist(raw: str) -> tuple[dict[str, list[str]] | None, str | None]:
    """Parse the JSON allowlist. Returns ``(mapping, error)``; error ⇒ deny-all."""
    if not raw.strip():
        return None, None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {ALLOWLIST_ENV}: {exc.msg} (line {exc.lineno})"
    if not isinstance(parsed, dict):
        return None, f"{ALLOWLIST_ENV} must be a JSON object of tenant -> tool list"
    mapping: dict[str, list[str]] = {}
    for tenant, value in parsed.items():
        if not isinstance(tenant, str) or not isinstance(value, list):
            return None, f"{ALLOWLIST_ENV}[{tenant!r}] must be a list of tool names"
        mapping[tenant] = [str(item) for item in value]
    return mapping, None


def _selected_names(
    allowlist: dict[str, list[str]] | None, tenant_id: str
) -> tuple[list[str] | None, str, list[str]]:
    """Pick the allowlist slice for this tenant.

    ``None`` means "no allowlist configured" — callers then fall back to the
    policy-derived default. ``"*"`` covers tenants without their own entry.
    """
    if allowlist is None:
        return None, _ALLOWLIST_UNSET, []
    if tenant_id in allowlist:
        return allowlist[tenant_id], f"tenant:{tenant_id}", []
    if "*" in allowlist:
        return allowlist["*"], "wildcard", []
    return [], "deny:no-matching-tenant", []


def tenant_tool_view(tenant_id: str) -> TenantToolView:
    """Build the per-tenant manifest. Never raises: bad config denies, loudly."""
    tenant = (tenant_id or "").strip()
    if not agent_tools_enabled():
        return TenantToolView(
            enabled=False,
            tenant_id=tenant,
            allowlist_source="disabled",
        )

    allowlist, error = _parse_allowlist(os.environ.get(ALLOWLIST_ENV, ""))
    selected, source, _ = _selected_names(allowlist, tenant)
    if error:
        logger.error(f"[agent_tools] {error} — denying every tool for tenant={tenant or '<unknown>'}")
        return TenantToolView(
            enabled=True,
            tenant_id=tenant,
            allowlist_source="error:deny-all",
            allowlist_error=error,
        )

    registry = tool_registry()
    candidates = list(registry) if selected is None else [n for n in selected]
    ignored = sorted({n for n in candidates if n not in registry})

    tools: list[dict[str, Any]] = []
    for name in candidates:
        if name not in registry:
            continue
        entry = openai_tool_entry(name)
        if entry is None:
            # গভর্নড রেজিস্ট্রিতে আছে কিন্তু spec নেই — নীরবে বাদ নয়, ত্রুটি।
            logger.error(f"[agent_tools] governed tool {name!r} has no OpenAI spec — hidden")
            continue
        decision, risk = evaluate_tool(name)
        auto_allowed = decision == "ALLOW"
        if selected is None and not auto_allowed:
            # ডিফল্ট-শাখা: কেবল অটো-অনুমোদিত টুল (fail-closed)।
            continue
        tools.append(
            {
                **entry,
                "agent": {
                    "available": auto_allowed,
                    "policy": decision,
                    "risk": risk,
                    "reason": None
                    if auto_allowed
                    else (
                        f"policy decision '{decision}' (risk {risk}) — requires human "
                        "approval, and chat has no approval hook yet"
                    ),
                },
            }
        )

    tools.sort(key=lambda item: item["function"]["name"])
    return TenantToolView(
        enabled=True,
        tenant_id=tenant,
        allowlist_source=source,
        tools=tools,
        ignored_allowlist_entries=ignored,
    )


def tool_declaration_count() -> int:
    """Number of declared tools — used by the drift guard against the registry."""
    return len(TOOL_SPECS)
