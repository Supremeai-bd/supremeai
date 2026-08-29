#!/usr/bin/env python3
import sys
import json
import fnmatch
from pathlib import Path
import yaml
from loguru import logger

def matches_pattern(file_path: str, patterns: list) -> bool:
    """Check if file_path matches any of the glob patterns."""
    for p in patterns:
        if p.endswith("/**"):
            p = p[:-3] + "*"
        if fnmatch.fnmatch(file_path, f"*{p}*"):
            return True
        if p in file_path:
            return True
    return False

def main():
    if len(sys.argv) < 3:
        logger.error("Usage: coverage_quality_gate.py <coverage.json> <policy.yaml>")
        sys.exit(1)

    cov_file = sys.argv[1]
    policy_file = sys.argv[2]

    try:
        with open(policy_file) as f:
            policy = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load policy.yaml: {e}")
        sys.exit(1)

    try:
        with open(cov_file) as f:
            coverage_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load coverage JSON: {e}")
        sys.exit(1)

    thresholds = policy.get("thresholds", {})
    critical_patterns = policy.get("critical", [])
    important_patterns = policy.get("important", [])

    overall_pr_thresh = thresholds.get("overall", {}).get("pr", 30)
    critical_pr_thresh = thresholds.get("critical", {}).get("pr", 80)
    important_pr_thresh = thresholds.get("important", {}).get("pr", 60)

    # Note: For now we enforce PR thresholds. In a real CI, we might check an env var for Release.

    files = coverage_data.get("files", {})
    
    total_statements = coverage_data.get("totals", {}).get("num_statements", 0)
    covered_statements = coverage_data.get("totals", {}).get("covered_lines", 0)
    
    overall_coverage = coverage_data.get("totals", {}).get("percent_covered", 0.0)

    critical_stmts = 0
    critical_covered = 0
    important_stmts = 0
    important_covered = 0

    for file_path, info in files.items():
        summary = info.get("summary", {})
        stmts = summary.get("num_statements", 0)
        cov_lines = summary.get("covered_lines", 0)
        
        # Determine tier
        is_crit = matches_pattern(file_path, critical_patterns)
        if is_crit:
            critical_stmts += stmts
            critical_covered += cov_lines
            continue
            
        is_imp = matches_pattern(file_path, important_patterns)
        if is_imp:
            important_stmts += stmts
            important_covered += cov_lines

    critical_cov_pct = (critical_covered / critical_stmts * 100) if critical_stmts else 100.0
    important_cov_pct = (important_covered / important_stmts * 100) if important_stmts else 100.0

    failed = False

    logger.info("=========================================")
    logger.info("   SUPREMEAI MULTI-LAYER COVERAGE GATE   ")
    logger.info("=========================================")

    # 1. Overall
    logger.info(f"Overall Coverage: {overall_coverage:.2f}% (Threshold: {overall_pr_thresh}%)")
    if overall_coverage < overall_pr_thresh:
        logger.error(f"❌ Overall coverage {overall_coverage:.2f}% is below {overall_pr_thresh}%")
        failed = True
    else:
        logger.info(f"✅ Overall coverage passed.")

    # 2. Critical
    logger.info(f"Critical Modules Coverage: {critical_cov_pct:.2f}% (Threshold: {critical_pr_thresh}%)")
    if critical_cov_pct < critical_pr_thresh:
        logger.error(f"❌ Critical coverage {critical_cov_pct:.2f}% is below {critical_pr_thresh}%")
        failed = True
    else:
        logger.info(f"✅ Critical coverage passed.")

    # 3. Important
    logger.info(f"Important Modules Coverage: {important_cov_pct:.2f}% (Threshold: {important_pr_thresh}%)")
    if important_cov_pct < important_pr_thresh:
        logger.warning(f"⚠️ Important coverage {important_cov_pct:.2f}% is below {important_pr_thresh}%")
        # According to test_coverage.md, PR gate is >=60%. 
        # But failing on important might be too harsh if we are just starting. Let's strictly enforce based on the file.
        logger.error(f"❌ Failing CI due to low Important coverage.")
        failed = True
    else:
        logger.info(f"✅ Important coverage passed.")

    logger.info("=========================================")
    
    if failed:
        logger.error("Quality Gate FAILED. Please add tests for your changes.")
        sys.exit(1)
    else:
        logger.info("Quality Gate PASSED. Great job!")
        sys.exit(0)

if __name__ == "__main__":
    main()
