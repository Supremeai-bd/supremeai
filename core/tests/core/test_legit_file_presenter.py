"""Unit tests for NaturalFilePresenter (Anti-Bot Organic Filename and Title Presentation).

বাংলা সারসংক্ষেপ:
------------------
অ্যান্টি-বট এড়ানোর জন্য রোবোটিক ফাইলনেম ও কনভারসেশন টাইটেলকে
মানুষের মতো স্বাভাবিক অর্গানিক (Natural) ফাইলে রূপান্তর যাচাই।
ইউজার নীতি: "legit kora mane name e legit add kora na... name dekhe mone hobe legit"
কোনো ফাইলের নামে যেন 'legit', 'fake', 'dummy' না থাকে।
"""

from __future__ import annotations

from core.natural_file_presenter import LegitFilePresenter, NaturalFilePresenter


def test_is_bot_like_name():
    """বাংলা মন্তব্য: বিভিন্ন রোবোটিক ও কৃত্রিম ফাইলনেম শনাক্তকরণ টেস্ট।"""
    # রোবোটিক ও কৃত্রিম নাম
    assert NaturalFilePresenter.is_bot_like_name("tmp_12345.txt") is True
    assert NaturalFilePresenter.is_bot_like_name("temp_script.py") is True
    assert NaturalFilePresenter.is_bot_like_name("agent_dump.json") is True
    assert NaturalFilePresenter.is_bot_like_name("scratch_notes.md") is True
    assert NaturalFilePresenter.is_bot_like_name("task_99182.py") is True
    assert (
        NaturalFilePresenter.is_bot_like_name("4a8b1c2d-9876-4321-abcd-123456789abc.json") is True
    )

    # নামের ভেতর 'legit_' বা 'fake_' থাকলে তা-ও রোবোটিক হিসেবে চিহ্নিত হবে
    assert NaturalFilePresenter.is_bot_like_name("legit_script.py") is True
    assert NaturalFilePresenter.is_bot_like_name("fake_data.json") is True

    # মানুষের মতো স্বাভাবিক খাঁটি নাম
    assert NaturalFilePresenter.is_bot_like_name("main.py") is False
    assert NaturalFilePresenter.is_bot_like_name("DashboardView.tsx") is False
    assert NaturalFilePresenter.is_bot_like_name("README.md") is False
    assert NaturalFilePresenter.is_bot_like_name("package.json") is False
    assert NaturalFilePresenter.is_bot_like_name("auth_service.py") is False


def test_naturalize_filename():
    """বাংলা মন্তব্য: রোবোটিক ফাইলনেমকে অর্গানিক ডেভেলপার ফাইলে রূপান্তর টেস্ট।"""
    # স্বাভাবিক নাম অপরিবর্তিত থাকবে
    assert NaturalFilePresenter.naturalize_filename("main.py") == "main.py"
    assert NaturalFilePresenter.naturalize_filename("index.css") == "index.css"

    # রোবোটিক নাম বদলে স্বাভাবিক এক্সটেনশনযুক্ত নাম আসবে
    natural_py = NaturalFilePresenter.naturalize_filename("tmp_18923.py")
    assert natural_py.endswith(".py")
    assert not NaturalFilePresenter.is_bot_like_name(natural_py)
    assert "legit" not in natural_py

    natural_json = NaturalFilePresenter.naturalize_filename("agent_task_dump.json")
    assert natural_json.endswith(".json")
    assert not NaturalFilePresenter.is_bot_like_name(natural_json)
    assert "legit" not in natural_json

    # ব্যাকওয়ার্ড কম্প্যাটিবিলিটি চেক (LegitFilePresenter.legitimize_filename)
    assert LegitFilePresenter.legitimize_filename("main.py") == "main.py"


def test_humanize_conversation_title():
    """বাংলা মন্তব্য: প্রম্পট থেকে মানুষের মতো স্বাভাবিক চ্যাট টাইটেল তৈরি টেস্ট।"""
    title = NaturalFilePresenter.humanize_conversation_title(
        "Refactor our FastAPI authentication endpoints with JWT verification"
    )
    assert len(title) > 0
    assert "Refactor" in title
    assert not NaturalFilePresenter.is_bot_like_name(title)
    assert "legit" not in title.lower()

    # রোবোটিক ও কৃত্রিম শব্দ বাদ দেওয়া
    cleaned_title = NaturalFilePresenter.humanize_conversation_title(
        "legit bot session task execute this query"
    )
    assert "bot" not in cleaned_title.lower()
    assert "session" not in cleaned_title.lower()
    assert "legit" not in cleaned_title.lower()


def test_content_aware_organic_naming():
    """বাংলা মন্তব্য: কোডের ভেতরের আসল ক্লাস ও ফাংশন দেখে নাম তৈরি যাচাই।"""
    # ১. পাইথন ক্লাসের নাম থেকে
    py_code = """
import os

class OrderProcessor:
    def __init__(self):
        pass
"""
    name = NaturalFilePresenter.naturalize_filename("tmp_18923.py", content=py_code)
    assert name == "order_processor.py"

    # ক্লাসের নামেও যদি কোনো কারণে legit_ থাকে, তাও ক্লিন হবে
    py_code_legit = """
class LegitPaymentGateway:
    def process(self):
        pass
"""
    name_clean = NaturalFilePresenter.naturalize_filename("tmp_pay.py", content=py_code_legit)
    assert name_clean == "payment_gateway.py"

    # ২. রিঅ্যাক্ট কম্পোনেন্টের নাম থেকে
    tsx_code = """
import React from 'react';

export function UserProfileCard() {
    return <div>User Card</div>;
}
"""
    name_tsx = NaturalFilePresenter.naturalize_filename("temp_comp.tsx", content=tsx_code)
    assert name_tsx == "UserProfileCard.tsx"

    # ৩. মার্কডাউন হেডিং থেকে
    md_doc = """
# System Deployment Architecture

This document describes the cloud setup.
"""
    name_md = NaturalFilePresenter.naturalize_filename("scratch_doc.md", content=md_doc)
    assert name_md == "system_deployment_architecture.md"

    # ৪. এসকিউএল টেবিল ক্রিয়েশন থেকে
    sql_code = """
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);
"""
    name_sql = NaturalFilePresenter.naturalize_filename("tmp_query.sql", content=sql_code)
    assert name_sql == "customers_schema.sql"


def test_humanize_prompt():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    রোবোটিক যান্ত্রিক প্রম্পটকে মানুষের মতো স্বাভাবিক ও সাধারণ প্রশ্নে রূপান্তর যাচাই।
    - "SYSTEM DIRECTIVE: ..." ছেঁটে ফেলে স্বাভাবিক প্রশ্ন রাখা
    - "STRICTLY ONLY OUTPUT CODE" কে মার্জিত অনুরোধে রূপান্তর
    """
    robotic_prompt = """SYSTEM DIRECTIVE: You are an autonomous coding bot.
Write a FastAPI route for user registration.
STRICTLY ONLY OUTPUT CODE. DO NOT EXPLAIN."""

    human_prompt = NaturalFilePresenter.humanize_prompt(robotic_prompt)

    assert "SYSTEM DIRECTIVE" not in human_prompt
    assert "Write a FastAPI route for user registration" in human_prompt
    valid_code_phrases = [
        "Just the clean code snippet would be great, thanks!",
        "Only need the code implementation, no extra commentary.",
        "Please output the clean code directly.",
        "Just the working code snippet please.",
    ]
    assert any(p in human_prompt for p in valid_code_phrases)
    assert "STRICTLY ONLY OUTPUT CODE" not in human_prompt

    # বাংলা মন্তব্য: 'Copy this to your AI:' থাকলে তা অটোনোমাস হিউম্যান ব্লুপ্রিন্ট হিসেবে অক্ষুণ্ণ থাকবে
    conductor_prompt = (
        "Copy this to your AI:\n"
        "You are an Autonomous Execution Agent.\n"
        "TASK TO EXECUTE:\n"
        "Refactor auth middleware to keep memory minimal."
    )
    preserved = NaturalFilePresenter.humanize_prompt(conductor_prompt)
    assert "Copy this to your AI:" in preserved
    assert "Autonomous Execution Agent" in preserved
    assert "Refactor auth middleware to keep memory minimal." in preserved

    # বাংলা মন্তব্য: অন্যান্য র্যান্ডমাইজড কনডাক্টর ভ্যারিয়েন্টও অবিকৃত থাকবে
    conductor_prompt2 = (
        "Copy and paste this into your AI chat:\n"
        "### IMPLEMENTATION TASK BRIEF\n"
        "TASK:\n"
        "Refactor auth middleware to keep memory minimal."
    )
    preserved2 = NaturalFilePresenter.humanize_prompt(conductor_prompt2)
    assert "Copy and paste this into your AI chat:" in preserved2
    assert "IMPLEMENTATION TASK BRIEF" in preserved2


def test_scrub_identity_and_watermarks():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    রেসপন্স স্ক্রাবার যাচাই:
    ১. সেলফ-আইডেন্টিটি ('I am Claude...', 'As ChatGPT...') ফিল্টার হওয়া
    ২. ইন্টারনাল থিংকিং ট্যাগ (<antThinking>, <thought>) মুছে যাওয়া
    ৩. রোবটিক ওপেনার ('Certainly! Here is...') মুছে যাওয়া
    """
    raw_response = (
        "<antThinking>The user needs a python function to add two numbers.</antThinking>\n"
        "Certainly! Here is the implementation:\n"
        "def add(a, b):\n"
        "    return a + b\n\n"
        "Generated by Claude 3.5 Sonnet"
    )

    clean = NaturalFilePresenter.scrub_identity_and_watermarks(raw_response)

    assert "<antThinking>" not in clean
    assert "Certainly!" not in clean
    assert "Generated by Claude" not in clean
    assert "def add(a, b):" in clean
    assert "return a + b" in clean

    raw_chatgpt = (
        "As an AI language model trained by OpenAI, I can help you with that.\n"
        "console.log('hello world');"
    )
    clean_chatgpt = NaturalFilePresenter.scrub_identity_and_watermarks(raw_chatgpt)
    assert "As an AI language model" not in clean_chatgpt
    assert "console.log('hello world');" in clean_chatgpt


def test_white_label_solution_and_code_comment_scrubbing():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    "কইয়ের তেলেই কই ভাজা, কিন্তু নিজের নামে মাছ বেচা" টেস্ট:
    ১. কোড কমেন্টে থার্ড-পার্টির ওয়াটারমার্ক (# Generated by ChatGPT) স্ক্রাব করা।
    ২. প্রোভাইডার নাম (Google Genkit, Anthropic Claude) স্বয়ংক্রিয়ভাবে SupremeAI ব্র্যান্ডে কনভার্ট হওয়া।
    """
    raw_code_output = (
        "Hello! I am Gemini, a large language model trained by Google.\n"
        "```python\n"
        "# Generated by ChatGPT 4o\n"
        "# Author: OpenAI Assistant\n"
        "def process_data(data):\n"
        "    return [d.strip() for d in data]\n"
        "```\n"
        "Built with Google Genkit pipeline."
    )

    clean_solution = NaturalFilePresenter.white_label_solution(
        raw_code_output, brand_name="SupremeAI"
    )

    # নিশ্চিত করা যে কোনো থার্ড পার্টি নাম নেই
    assert "I am Gemini" not in clean_solution
    assert "Generated by ChatGPT" not in clean_solution
    assert "OpenAI Assistant" not in clean_solution
    assert "Google Genkit" not in clean_solution
    # আসল কোড ঠিক থাকবে
    assert "def process_data(data):" in clean_solution
    assert "return [d.strip() for d in data]" in clean_solution
