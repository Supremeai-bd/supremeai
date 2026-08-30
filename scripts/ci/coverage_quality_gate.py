#!/usr/bin/env python3
import sys
import json
import fnmatch
import argparse
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
    parser = argparse.ArgumentParser(description="Evaluate coverage against policy thresholds.")
    parser.add_argument("cov_file", help="Path to coverage.json")
    parser.add_argument("policy_file", help="Path to coverage_policy.yaml")
    parser.add_argument("--tiers", default="overall,critical,important",
                        help="Comma-separated list of tiers to evaluate (e.g., 'critical,important')")
    args = parser.parse_args()

    active_tiers = [t.strip().lower() for t in args.tiers.split(",") if t.strip()]

    try:
        with open(args.policy_file) as f:
            policy = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load policy.yaml: {e}")
        sys.exit(1)

    try:
        with open(args.cov_file) as f:
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
    logger.info(f"   Active Tiers: {', '.join(active_tiers)}")
    logger.info("=========================================")

    # 1. Overall
    if "overall" in active_tiers:
        logger.info(f"Overall Coverage: {overall_coverage:.2f}% (Threshold: {overall_pr_thresh}%)")
        if overall_coverage < overall_pr_thresh:
            logger.error(f"❌ Overall coverage {overall_coverage:.2f}% is below {overall_pr_thresh}%")
            failed = True
        else:
            logger.info("✅ Overall coverage passed.")

    # 2. Critical
    if "critical" in active_tiers:
        logger.info(f"Critical Modules Coverage: {critical_cov_pct:.2f}% (Threshold: {critical_pr_thresh}%)")
        if critical_cov_pct < critical_pr_thresh:
            logger.error(f"❌ Critical coverage {critical_cov_pct:.2f}% is below {critical_pr_thresh}%")
            failed = True
        else:
            logger.info("✅ Critical coverage passed.")

    # 3. Important
    if "important" in active_tiers:
        logger.info(f"Important Modules Coverage: {important_cov_pct:.2f}% (Threshold: {important_pr_thresh}%)")
        if important_cov_pct < important_pr_thresh:
            logger.error(f"❌ Important coverage {important_cov_pct:.2f}% is below {important_pr_thresh}%")
            failed = True
        else:
            logger.info("✅ Important coverage passed.")

    logger.info("=========================================")
    
    if failed:
        logger.error("Quality Gate FAILED. Please add tests for your changes.")
        sys.exit(1)
    else:
        logger.info("Quality Gate PASSED. Great job!")
        sys.exit(0)

if __name__ == "__main__":
    main()
