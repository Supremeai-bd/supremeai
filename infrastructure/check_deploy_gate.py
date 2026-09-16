import sys

from google.cloud import firestore
from loguru import logger


def verify_deployment_gate():
    logger.info(
        "🔍 CI/CD Gatekeeper: Auditing SupremeAI 2.0 autonomous deployment gate status..."
    )

    try:
        db = firestore.Client()
        gate_ref = db.collection("deploy_gate").document("status")
        doc = gate_ref.get()

        if not doc.exists:
            # FIX(fail-closed): a missing gate document previously defaulted to
            # SAFE/UNLOCKED and exited 0 — meaning anyone (or any outage:
            # wrong project, revoked credentials scope, deleted doc) could
            # silently bypass the deployment gate. Absence of evidence of an
            # unlocked gate must LOCK deployment, not unlock it.
            logger.critical(
                "❌ Deploy gate status document NOT found (deploy_gate/status). "
                "Defaulting to LOCKED — deployment blocked. "
                "To proceed, create the Firestore document explicitly with "
                'status="UNLOCKED" and a reason.'
            )
            sys.exit(1)

        gate_data = doc.to_dict() or {}
        # FIX(fail-closed): missing/unset status field now locks as well —
        # previously .get("status", "UNLOCKED") treated a malformed document
        # as an explicit approval.
        status = str(gate_data.get("status", "LOCKED")).upper()
        reason = gate_data.get("reason", "No reason provided.")
        updated_at = gate_data.get("updated_at", "Unknown time")

        if status == "LOCKED":
            logger.critical("❌" * 20)
            logger.critical("🚨 DEPLOYMENT REJECTED! The autonomous gate is LOCKED.")
            logger.critical(f"📝 Reason: {reason}")
            logger.critical(f"⏰ Last Audit Update: {updated_at}")
            logger.critical("❌" * 20)
            # Exit code 1 দিয়ে সিআই/সিডি পাইপলাইনকে এখানেই থামিয়ে দেওয়া হবে
            sys.exit(1)

        logger.info(
            f"🟢 DEPLOYMENT APPROVED. Autonomous gate status is UNLOCKED. (Reason: {reason})"
        )
        sys.exit(0)

    except Exception as e:
        logger.critical(
            f"⚠️ Gatekeeper failed to query Firestore: {e!s}. Locking deployment for safety."
        )
        sys.exit(1)


if __name__ == "__main__":
    verify_deployment_gate()
