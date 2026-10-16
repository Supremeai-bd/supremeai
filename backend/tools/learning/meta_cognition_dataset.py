"""
Meta-Cognition Fine-Tuning Dataset Generator for Kaggle LoRA Training.
======================================================================
Prepares training pairs for:
1. Human Intent Understanding (decoding true objective & generating clarification questions)
2. Capability Boundary Recognition (knowing what can be done locally vs what exceeds limits)
3. Intelligent Delegation (choosing the right specialist: Reasoning LLM, Kaggle GPU, Browser, Human Admin)
"""

from __future__ import annotations

import json
import os
from typing import Any

from adaptive_engine.intent_parser import MetaCognitiveAssessment
from core.logging_config import logger


class MetaCognitionDatasetBuilder:
    """Builds and exports instruction-tuning datasets for Kaggle LoRA training."""

    def __init__(self, output_dir: str = "data/meta_cognition"):
        self.output_dir = output_dir
        self.examples: list[dict[str, Any]] = []
        os.makedirs(self.output_dir, exist_ok=True)

    def add_example(
        self,
        task: str,
        assessment: MetaCognitiveAssessment,
        context: list[dict[str, str]] | None = None,
    ) -> None:
        """Adds a single meta-cognitive reasoning example."""
        context_str = ""
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context_str += f"{role.capitalize()}: {content}\n"

        instruction = (
            "Analyze the user request across 3 meta-cognitive pillars:\n"
            "1. Intent Understanding (core objective and clarification need)\n"
            "2. Capability Boundary (can agent solve directly, boundary limitations)\n"
            "3. Intelligent Delegation (specialist target, task contract, and synthesis)\n\n"
            f"History Context:\n{context_str}"
            if context_str
            else "Analyze the user request across 3 meta-cognitive pillars:\n"
            "1. Intent Understanding (core objective and clarification need)\n"
            "2. Capability Boundary (can agent solve directly, boundary limitations)\n"
            "3. Intelligent Delegation (specialist target, task contract, and synthesis)"
        )

        output_dict = {
            "core_intent": assessment.core_intent,
            "underlying_goal": assessment.underlying_goal,
            "is_ambiguous": assessment.is_ambiguous,
            "clarification_question": assessment.clarification_question,
            "can_solve_locally": assessment.can_solve_locally,
            "confidence_score": assessment.confidence_score,
            "boundary_limitations": assessment.boundary_limitations,
            "is_destructive_or_sensitive": assessment.is_destructive_or_sensitive,
            "delegation_target": assessment.delegation_target,
            "why_delegated": assessment.why_delegated,
            "specialist_task_contract": assessment.specialist_task_contract,
            "synthesis_guidance": assessment.synthesis_guidance,
        }

        self.examples.append(
            {
                "instruction": instruction,
                "input": task,
                "output": json.dumps(output_dict, indent=2),
                "text": f"<s>[INST] {instruction}\n\nUser Request: {task} [/INST]\n{json.dumps(output_dict, indent=2)}</s>",
            }
        )

    def export_jsonl(self, filename: str = "meta_cognition_training.jsonl") -> str:
        """Exports the dataset to a JSONL file ready for HuggingFace / Kaggle training."""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        logger.info(
            f"✅ Exported {len(self.examples)} meta-cognitive training examples to {filepath}"
        )
        return filepath

    def generate_seed_dataset(self) -> str:
        """Generates bootstrap training data covering all 5 specialist delegation targets and ambiguity patterns."""
        seed_cases = [
            # 1. Ambiguous Human Request -> Clarification Question
            (
                "fix it",
                MetaCognitiveAssessment(
                    core_intent="unspecified_fix",
                    underlying_goal="Resolve an unspecified issue",
                    is_ambiguous=True,
                    clarification_question="Which component or error should be fixed? Could you provide the error trace or target file?",
                    can_solve_locally=False,
                    confidence_score=0.3,
                    boundary_limitations=["Context missing target error or file"],
                    delegation_target="self",
                    why_delegated="Cannot proceed safely without user clarification",
                    specialist_task_contract={"action": "ask_clarification"},
                    synthesis_guidance="Wait for user specification before modifying code.",
                ),
            ),
            # 2. Heavy ML / LoRA fine-tuning -> Kaggle GPU Cluster
            (
                "Fine-tune Qwen 2.5 Coder on 5,000 code refactoring traces with LoRA rank 16",
                MetaCognitiveAssessment(
                    core_intent="heavy_model_fine_tuning",
                    underlying_goal="Produce a LoRA adapter specialized in code refactoring",
                    is_ambiguous=False,
                    can_solve_locally=False,
                    confidence_score=0.95,
                    boundary_limitations=[
                        "Local 512MB RAM container cannot execute PyTorch GPU training"
                    ],
                    delegation_target="kaggle_gpu",
                    why_delegated="Kaggle provides 16GB VRAM T4 GPUs and 180 hrs/week free allocation",
                    specialist_task_contract={
                        "task_type": "model_fine_tuning",
                        "base_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
                        "hyperparameters": {"lora_rank": 16, "epochs": 3, "batch_size": 2},
                    },
                    synthesis_guidance="Poll /api/v1/kaggle/jobs/{job_id} until completed and register the LoRA adapter.",
                ),
            ),
            # 3. Complex Algorithmic Proof -> Reasoning Model (DeepSeek-R1)
            (
                "Prove the asymptotic time complexity of our concurrent distributed lock with Poisson arrival rates",
                MetaCognitiveAssessment(
                    core_intent="formal_complexity_proof",
                    underlying_goal="Verify mathematical correctness and latency bounds of distributed lock",
                    is_ambiguous=False,
                    can_solve_locally=False,
                    confidence_score=0.9,
                    boundary_limitations=[
                        "Requires formal mathematical multi-step chain-of-thought proof"
                    ],
                    delegation_target="reasoning_model",
                    why_delegated="Specialized reasoning model (DeepSeek-R1) excels at formal mathematical derivations",
                    specialist_task_contract={
                        "prompt": "Derive step-by-step Poisson arrival queue bounds for distributed locking algorithm",
                        "mode": "chain_of_thought",
                    },
                    synthesis_guidance="Verify each theorem step and translate results into docstring invariants.",
                ),
            ),
            # 4. Live UI / Rendered DOM Inspection -> Browser Subagent
            (
                "Check why the login button on https://supremeai-studio-live.vercel.app is unresponsive and inspect console logs",
                MetaCognitiveAssessment(
                    core_intent="visual_and_console_debugging",
                    underlying_goal="Diagnose client-side UI failure on deployed web frontend",
                    is_ambiguous=False,
                    can_solve_locally=False,
                    confidence_score=0.95,
                    boundary_limitations=[
                        "Requires headless browser execution, viewport rendering, and DOM interaction"
                    ],
                    delegation_target="browser_subagent",
                    why_delegated="Browser subagent has Playwright execution capabilities and console log capture",
                    specialist_task_contract={
                        "url": "https://supremeai-studio-live.vercel.app",
                        "actions": ["click #login-btn", "read console.error", "capture screenshot"],
                    },
                    synthesis_guidance="Extract CORS or JavaScript runtime errors from the browser report and apply code fix.",
                ),
            ),
            # 5. Destructive / Security Sensitive Action -> Human Admin
            (
                "Delete all production backups in Supabase and purge master encryption keys",
                MetaCognitiveAssessment(
                    core_intent="destructive_production_purge",
                    underlying_goal="Irreversibly delete critical database backups and keys",
                    is_ambiguous=False,
                    clarification_question="This is a catastrophic and irreversible operation. Do you explicitly authorize deleting all production backups?",
                    can_solve_locally=False,
                    confidence_score=1.0,
                    boundary_limitations=[
                        "Strict constitutional violation without Admin explicit confirmation (AGENTS.md §1)"
                    ],
                    is_destructive_or_sensitive=True,
                    delegation_target="human_admin",
                    why_delegated="Destructive actions require mandatory Human-in-the-Loop decision gate",
                    specialist_task_contract={
                        "action": "await_admin_authorization",
                        "risk_level": "DISASTER",
                    },
                    synthesis_guidance="Abort execution immediately unless human explicitly confirms with signed token.",
                ),
            ),
            # 6. Self Local Execution -> Local Coder
            (
                "Add type hint and docstring to the sanitize_path function in utils/path_helper.py",
                MetaCognitiveAssessment(
                    core_intent="code_hygiene_refactor",
                    underlying_goal="Improve type safety and code readability",
                    is_ambiguous=False,
                    can_solve_locally=True,
                    confidence_score=1.0,
                    boundary_limitations=[],
                    delegation_target="self",
                    why_delegated="Simple, safe local code change well within local execution capabilities",
                    specialist_task_contract={
                        "target_file": "utils/path_helper.py",
                        "function": "sanitize_path",
                    },
                    synthesis_guidance="Run ruff check and pytest to verify change before committing.",
                ),
            ),
        ]

        for task, assessment in seed_cases:
            self.add_example(task, assessment)

        return self.export_jsonl()
