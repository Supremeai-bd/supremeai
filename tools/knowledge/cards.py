from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

class ToolKnowledgeCard:
    tool_id: str
    tool_name: str
    category: str                   # RADAR | SHIELD | ENGINE | ORCHESTRATOR | MEMORY | EVOLUTION
    file_path: str
    intent_triggers: List[str]      # Semantic keywords that invoke this tool
    cognitive_intents: List[str]    # REPAIR | SYNTHESIS | AUDIT | EVOLUTION
    description: str
    when_to_use: str
    when_not_to_use: str
    inputs: List[str]
    outputs: List[str]
    chain_before: List[str]         # Tools that should run BEFORE this
    chain_after: List[str]          # Tools that should run AFTER this
    cli_example: str
    confidence_weight: float        # How reliable this tool is (0.0-1.0)
    cost_tokens: str                # "zero" | "low" | "medium" | "high"
    requires_network: bool
    version: str = "1.0.0"          # Semantic version; auto-bumped on content hash change
    tags: List[str] = field(default_factory=list)

    def to_memory_content(self) -> str:
        """Generate rich textual knowledge for vector embedding."""
        return f"""
TOOL: {self.tool_name}
CATEGORY: {self.category}
FILE: {self.file_path}

DESCRIPTION: {self.description}

WHEN TO USE: {self.when_to_use}
WHEN NOT TO USE: {self.when_not_to_use}

INTENT TRIGGERS: {', '.join(self.intent_triggers)}
COGNITIVE INTENTS: {', '.join(self.cognitive_intents)}

INPUTS: {'; '.join(self.inputs)}
OUTPUTS: {'; '.join(self.outputs)}

CHAIN BEFORE THIS TOOL: {', '.join(self.chain_before) if self.chain_before else 'none'}
CHAIN AFTER THIS TOOL: {', '.join(self.chain_after) if self.chain_after else 'none'}

CLI EXAMPLE: {self.cli_example}
CONFIDENCE: {self.confidence_weight}
NETWORK REQUIRED: {self.requires_network}
TOKEN COST: {self.cost_tokens}
TAGS: {', '.join(self.tags)}
""".strip()

    def to_summary(self) -> str:
        return f"[{self.category}] {self.tool_name}: {self.description[:120]}"