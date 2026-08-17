# tests/test_file_gate_run.py
import logging
import sys
from backend.sandbox.file_isolation_gate import FileIsolationGate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("supremeai.test_gate")


def run_gate_test():
    logger.info("🎬 Initializing Sandbox File Isolation Gate Integration Test...")
    gate = FileIsolationGate()

    # টেস্ট ডাটা প্রিপারেশন (৫২ বাইটের মক ফাইল)
    fake_pdf_bytes = b"SupremeAI Secure Manifesto 2026. Sandbox Enforced Content."

    # রান পাইপলাইন
    res = gate.execute_file_parsing_safely(
        raw_file_bytes=fake_pdf_bytes, file_extension="pdf"
    )
    logger.info(f"Gate Transaction Status: {res.get('success')}")
    logger.info(f"Sandbox Runtime Raw Output: {res.get('sandbox_output')}")


if __name__ == "__main__":
    run_gate_test()
