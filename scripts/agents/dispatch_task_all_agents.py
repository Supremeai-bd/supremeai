"""SupremeAI Task Dispatcher: Send START_TASK messages to all active agents.

Dispatches direct messages and topic broadcasts across all active agent slots
using SupremeAI Mesh AgentMailbox.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Set test bypass for environment safely
os.environ["TESTING"] = "true"
os.environ["ENV"] = "test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ALLOW_TEST_AUTH_BYPASS"] = "true"

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
sys.path.insert(0, os.path.abspath(backend_path))

load_dotenv()

from core.agent_mailbox import get_agent_mailbox, BROADCAST_TARGET


async def dispatch_tasks():
    print("=" * 70)
    print(" SupremeAI Multi-Agent Task Dispatcher")
    print("=" * 70)

    mailbox = await get_agent_mailbox()
    tenant_id = "tenant-supremeai"
    sender = "orchestrator-main"

    active_agents = {
        "agent-5": {
            "role": "planner",
            "task": "Review GitHub issues queue (#1439, #1438, #1421), create structured handoff plans",
        },
        "agent-6": {
            "role": "coder-1",
            "task": "Claim open implementation issues, write code & tests, open PR",
        },
        "agent-7": {
            "role": "coder-2",
            "task": "Solve parallel tasks, inspect open PRs, run regression check and merge green PRs",
        },
        "agent-8": {
            "role": "pr-helper",
            "task": "Verify PR compliance, check test coverage, keep heartbeat dashboard online",
        },
        "agent-10": {
            "role": "orchestrator",
            "task": "Monitor mesh health, supervise slot allocation, maintain platform heartbeat",
        },
        "agent-11": {
            "role": "platform-agent",
            "task": "Execute 3h platform health sweep, remediate Issue #1534 failure",
        },
        "agent-12": {
            "role": "ci-action",
            "task": "Watch GitHub Actions workflow runs, trigger E2E smoke suite on merge",
        },
    }

    # 1. Topic Subscriptions
    print("\n[Step 1] Subscribing agents to topics...")
    for agent_id in active_agents:
        await mailbox.subscribe(
            agent_id=agent_id,
            topics=["task-dispatch", "general"],
            tenant_id=tenant_id,
        )
    print(f" -> Subscribed {len(active_agents)} agents to 'task-dispatch' & 'general'.")

    # 2. Broadcast Message to ALL agents
    print("\n[Step 2] Sending Broadcast Signal to ALL agents...")
    broadcast_body = {
        "intent": "START_TASK",
        "priority": "HIGH",
        "message": "All active agent slots: commence assigned workflows and report status.",
        "active_slots": list(active_agents.keys()),
    }
    broadcast_msg = await mailbox.send(
        from_agent=sender,
        to_agent=BROADCAST_TARGET,
        tenant_id=tenant_id,
        topic="task-dispatch",
        body=broadcast_body,
    )
    print(f" -> Broadcast sent! ID: {broadcast_msg.message_id}")

    # 3. Direct Targeted Messages to Each Agent Slot
    print("\n[Step 3] Sending Direct Task Assignments to Active Agents...")
    dispatched = []
    for agent_id, details in active_agents.items():
        direct_body = {
            "intent": "ASSIGN_TASK",
            "slot": agent_id,
            "role": details["role"],
            "instruction": details["task"],
            "status": "IN_PROGRESS",
            "governing_rule": "AGENTS.md Core Loop",
        }
        res = await mailbox.send(
            from_agent=sender,
            to_agent=agent_id,
            tenant_id=tenant_id,
            topic="task-dispatch",
            body=direct_body,
        )
        dispatched.append((agent_id, res.message_id, details["role"]))
        print(f" -> [{agent_id}] ({details['role']}): Dispatched Message {res.message_id}")

    # 4. Verify inboxes
    print("\n[Step 4] Verifying Inboxes...")
    for agent_id in active_agents:
        inbox = await mailbox.inbox(
            agent_id=agent_id,
            tenant_id=tenant_id,
            unread_only=True,
        )
        print(f" -> {agent_id}: {len(inbox)} message(s) waiting in inbox.")

    print("\n" + "=" * 70)
    print(" All active agents notified and task signals dispatched successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(dispatch_tasks())
