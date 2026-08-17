# tests/test_live_morphic_run.py
import os
import json
import logging
import sys
from backend.skills.core_knowledge_qa import execute_tool

# লগিং কনফিগারেশন (যাতে কনসোলে আউটপুট সুন্দরভাবে দেখা যায় এবং লিন্টার পাস করে)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("supremeai.test_runner")


def run_rag_rbac_matrix_test():
    logger.info("🚀 Initiating SupremeAI RAG & RBAC Validation Suite...")
    logger.info("📅 Enforcing Current System Timeline Context: 2026")
    logger.info("=" * 60)

    # 🎯 TEST CASE 1: Admin Requesting Classified Financials
    logger.info("🔒 [CASE 1] Requesting Classified Financials as 'Admin'...")
    payload_admin = {
        "user_role": "Admin",
        "query": "What was the net profit margin trend in Q1 2026?",
    }
    res_admin = execute_tool(payload_admin)
    logger.info(f"Response Status: {res_admin.get('success')}")

    if res_admin.get("success"):
        logger.info(f"🤖 AI Answer: {res_admin['result']['answer']}")
        logger.info(
            f"📄 Citations: {json.dumps(res_admin['result']['citations'], indent=2)}"
        )
    else:
        logger.error(f"❌ Error: {res_admin.get('error')}")

    logger.info("=" * 60)

    # 🎯 TEST CASE 2: Standard_User Requesting Classified Financials (Should be Blocked)
    logger.info("🛑 [CASE 2] Requesting Classified Financials as 'Standard_User'...")
    payload_unauth = {
        "user_role": "Standard_User",
        "query": "What was the net profit margin trend in Q1 2026?",
    }
    res_unauth = execute_tool(payload_unauth)
    logger.info(f"Response Status: {res_unauth.get('success')}")

    if res_unauth.get("success"):
        logger.info(f"🤖 AI Answer: {res_unauth['result']['answer']}")
        logger.info(
            f"📄 Citations Appended Count: {len(res_unauth['result']['citations'])}"
        )
    else:
        logger.error(f"❌ Error: {res_unauth.get('error')}")

    logger.info("=" * 60)

    # 🎯 TEST CASE 3: Standard_User Requesting Allowed Public SOPs
    logger.info("🟢 [CASE 3] Requesting Public SOPs as 'Standard_User'...")
    payload_public = {
        "user_role": "Standard_User",
        "query": "What are the official timing rules and remote work rules for SupremeAI?",
    }
    res_public = execute_tool(payload_public)
    logger.info(f"Response Status: {res_public.get('success')}")

    if res_public.get("success"):
        logger.info(f"🤖 AI Answer: {res_public['result']['answer']}")
        logger.info(
            f"📄 Citations: {json.dumps(res_public['result']['citations'], indent=2)}"
        )
    else:
        logger.error(f"❌ Error: {res_public.get('error')}")


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        logger.warning("⚠️ GEMINI_API_KEY environment variable is not set!")
    run_rag_rbac_matrix_test()
