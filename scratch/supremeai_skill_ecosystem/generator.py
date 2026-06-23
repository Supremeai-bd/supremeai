#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> generator.py
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> scratch
# ============================================================================
import os
import json
from pathlib import Path
from langchain.llms import OpenAI
from skill_schema import validate_skill

llm = OpenAI(model="gpt-oss-120b", temperature=0.2)

def generate_skill(prompt: str) -> dict:
    tmpl = f"""
    You are a SupremeAI skill JSON generator. Follow this exact format:
    {{
        "metadata": {{
            "name": "<skill_name>",
            "version": "v1.0",
            "description": "<short description>",
            "author": "SupremeAI"
        }},
        "inputs": [{{"name":"input1","type":"string","required":true}}],
        "outputs": [{{"name":"output1","type":"string"}}],
        "implementation": {{
            "language":"python",
            "code":"def run(input1):\\n    return f'Hello {{input1}}'"
        }}
    }}
    Prompt: {prompt}
    """
    resp = llm.invoke(tmpl)
    skill = json.loads(resp)
    validate_skill(skill)
    return skill

def save_skill(skill: dict, path: Path):
    path.write_text(json.dumps(skill, indent=2, ensure_ascii=False))
    print(f"Skill saved -> {path}")

if __name__ == "__main__":
    user_prompt = "Create a skill to send cart abandonment emails for Shopify"
    skill = generate_skill(user_prompt)
    save_skill(skill, Path(__file__).with_name("sample_skill.json"))
