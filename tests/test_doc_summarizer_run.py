# tests/test_doc_summarizer_run.py
import os
import logging
import sys
import time
from backend.skills.core_doc_summarizer import execute_tool

# প্রোডাকশন-গ্রেড লগিং সেটআপ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("supremeai.test_summarizer")


def run_summarizer_benchmark_suite():
    logger.info(
        "🚀 Initiating Document Summarization & File Intelligence Test Suite..."
    )
    logger.info("📅 Context Timeline Enforced: 2026")
    logger.info("=" * 70)

    # --- TEST CASE 1: Standard Corporate SOP (Under 100k Limit) ---
    logger.info("🟢 [CASE 1] Processing Valid Corporate Document (Concise Mode)...")
    valid_sop_text = (
        "SupremeAI Operations Manifesto 2026.\n"
        "1. Executive Objective: Scale autonomous multi-agent orchestration by 400% in Q3.\n"
        "2. Infrastructure Guardrails: All external third-party executable code must undergo "
        "Morphic transformation and be executed within isolated temporary Docker runtimes.\n"
        "3. Financial Protocol: Budget thresholds per API call are hardcoded to $0.05 max.\n"
        "4. Action Item: Infrastructure team must migrate all database connection strings "
        "to Supavisor connection pooling on port 6543 before the next production sync."
    )

    payload_valid = {"file_content": valid_sop_text, "summary_length": "concise"}

    start_time = time.time()
    res_valid = execute_tool(payload_valid)
    latency_valid = time.time() - start_time

    logger.info(f"Execution Status: {res_valid.get('success')}")
    if res_valid.get("success"):
        logger.info(f"⚡ Latency: {latency_valid:.2f} seconds")
        logger.info(
            f"📦 Bytes Processed: {res_valid['result']['extracted_bytes_processed']} bytes"
        )
        logger.info(
            f"🤖 AI Document Intelligence Summary:\n{res_valid['result']['summary']}"
        )
    else:
        logger.error(f"❌ Execution Anomaly: {res_valid.get('error')}")

    logger.info("=" * 70)

    # --- TEST CASE 2: Security Edge Case (Oversized Document Over 100k Chars) ---
    logger.info(
        "🛑 [CASE 2] Injecting Malicious/Oversized Document (Boundary Guard Check)..."
    )
    # ১০০,০০০ ক্যারেক্টার লিমিট ক্রস করানোর জন্য একটি বিশাল স্ট্রিং তৈরি
    oversized_text = (
        "SupremeAI Garbage Data Stream Content " * 3000
    )  # আনুমানিক ১,১৪,০০০ ক্যারেক্টার

    payload_oversized = {"file_content": oversized_text, "summary_length": "detailed"}

    res_oversized = execute_tool(payload_oversized)
    logger.info(f"Execution Status: {res_oversized.get('success')}")

    if not res_oversized.get("success"):
        logger.info(
            f"🛡️ Security Guard Success! Blocked Message: {res_oversized.get('error')}"
        )
    else:
        logger.error(
            "❌ Security Failure: Oversized document bypassed the 100k boundary guard!"
        )


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning(
            "⚠️ GEMINI_API_KEY is missing from environment. API call will fail."
        )
    run_summarizer_benchmark_suite()
