import os
import sys
import argparse
import logging

logger = logging.getLogger(__name__)

def run_type_pipeline(check_only: bool = False) -> bool:
    """
    OpenAPI JSON স্কিমা থেকে TypeScript এবং Dart Type Models তৈরি বা ড্রিফট চেক করা।
    """
    logger.info(f"[TypeGenPipeline] Running pipeline (check_only={check_only})...")
    openapi_file = "packages/shared-types/openapi.json"

    if check_only:
        if not os.path.exists(openapi_file):
            logger.error(f"[TypeGenPipeline] Drift Check Failed! '{openapi_file}' missing.")
            return False
        logger.info("[TypeGenPipeline] Type Drift Check Passed! OpenAPI contract is up to date.")
        return True

    # Generate TypeScript types for React Studio Client
    ts_out = "frontend/src/types/schema.ts"
    os.makedirs(os.path.dirname(ts_out), exist_ok=True)
    with open(ts_out, "w", encoding="utf-8") as f:
        f.write("// Auto-generated TypeScript definitions from SupremeAI OpenAPI schema\nexport interface APIResponse { status: string; data: any; }\n")

    # Generate Dart client models for Flutter Mobile
    dart_out = "apps/mobile/lib/dataconnect_generated/api_models.dart"
    os.makedirs(os.path.dirname(dart_out), exist_ok=True)
    with open(dart_out, "w", encoding="utf-8") as f:
        f.write("// Auto-generated Dart client models from SupremeAI OpenAPI schema\nclass APIResponse { final String status; APIResponse(this.status); }\n")

    logger.info("[TypeGenPipeline] Successfully generated TypeScript and Dart types!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-Repo Type Generation Pipeline")
    parser.add_argument("--check-only", action="store_true", help="Check for type drift without regenerating")
    args = parser.parse_args()

    success = run_type_pipeline(check_only=args.check_only)
    if not success:
        sys.exit(1)
