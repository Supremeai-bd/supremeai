import sys
import json
import asyncio
from pathlib import Path

# Fix Windows console unicode output
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def setup_env():
    backend_path = Path(__file__).resolve().parent.parent / "backend"
    sys.path.insert(0, str(backend_path))

async def run_guardian():
    setup_env()
    from core.agent_factory import DynamicAgentFactory
    from core.llm_gateway import llm_gateway

    # Load Guardian from Registry
    factory = DynamicAgentFactory()
    guardian_config = factory.get_registered_agent("guardian_expert")
    if not guardian_config:
        print("🚨 guardian_expert not found in AgentRegistry!")
        return

    print(f"🤖 Initializing {guardian_config['agent_name']}...")

    # Load agent_rules.json
    rules_path = Path(__file__).resolve().parent.parent / "agent_rules.json"
    if not rules_path.exists():
        print("🚨 agent_rules.json not found!")
        return

    with open(rules_path, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    # Get a quick summary of active rules
    active_rules = [r for r in rules_data.get("rules", []) if r.get("automatable")]
    rule_summaries = [f"{r['id']}: {r['description']}" for r in active_rules]

    print(f"📋 Loaded {len(active_rules)} automatable rules for compliance checking.")

    # In a real system, the Guardian would monitor PRs or receive a specific file diff.
    # Here, we will pick a sample file to demonstrate the agent's capability.
    sample_file = Path(__file__).resolve().parent / "cost_guard_monitor.py"
    if not sample_file.exists():
        print("No sample file to analyze.")
        return

    with open(sample_file, "r", encoding="utf-8") as f:
        code_content = f.read()

    system_prompt = guardian_config.get("system_prompt", "You are the Guardian Agent.")
    user_prompt = (
        "Analyze the following Python code against our project rules.\n\n"
        "### Project Rules:\n"
        + "\n".join(rule_summaries) + "\n\n"
        "### Code to Analyze (cost_guard_monitor.py):\n"
        "```python\n" + code_content + "\n```\n\n"
        "List any violations with their Rule ID. If there are no violations, report 'ALL CLEAR'."
    )

    print("🔍 Guardian is analyzing the codebase...")

    try:
        response = await llm_gateway.acompletion(
            model="gemini/gemini-2.5-pro", # Use an advanced model for analysis
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        report = response.get("choices", [{}])[0].get("message", {}).get("content", "Failed to generate report.")

        print("\n" + "="*50)
        print("🛡️ GUARDIAN AGENT REPORT")
        print("="*50)
        print(report)
        print("="*50)

    except Exception as e:
        print(f"🚨 Guardian analysis failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_guardian())
