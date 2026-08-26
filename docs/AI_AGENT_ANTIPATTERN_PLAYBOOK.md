# 📚 AI Agent Anti-Pattern Playbook v3.0

**Purpose**: Reduce AI audit errors by documenting anti-patterns, prevention rules, and validation checks  
**Created**: 2026-01-26  
**Last Updated**: 2026-01-26 (Triple-Source Cross-Verification)  
**Status**: **LIVING DOCUMENT** — Update after every audit cycle  
**Trigger Events**: 
- Super Z Audit v1.0 + User Manual Verification
- GPT Independent Reverification
- Combined error analysis and synthesis

---

## 🎯 Why This Playbook Exists

### The Problem We're Solving

Three independent audit sources found errors in each other:

| Source | Strengths | Critical Errors Found |
|--------|-----------|----------------------|
| **Super Z Audit v1** | 6 complete patches, user verification table, actionable ZIP | Count inconsistency (71/69/67), missed NEW-001~005, severity inflation |
| **User Manual Verification** | Source-level line-by-line check, Bengali+English analysis | Corrected C-04 overstated, C-02 had 1 FP, C-03 count was ~20 not ~40 |
| **GPT Reverification** | Caught count math, found 5 new issues, corrected SEC-004 | No patches, some technical misjudgments, ignored user context |

### Core Insights (From All Three Sources)

> **Insight #1**: "Two auditors make DIFFERENT errors — systematic reduction > perfection"  
> **Insight #2**: "Human source-level verification catches AI hallucination patterns"  
> **Insight #3**: "Count consistency is TABLE STAKES for professional audits"  
> **Insight #4**: "Severity calibration requires DOMAIN KNOWLEDGE, not generic rules"

---

## 🔴 COMPREHENSIVE ANTI-PATTERN CATALOGUE

### Category 1: COUNT & CONSISTENCY ERRORS

#### ❌ ANTI-PATTERN AP-001: "Magic Number Syndrome"

**Description**: Reporting different finding counts in different sections without cross-validation.

**Real Example (Super Z Audit)**:
```
Executive Summary:     "71 Issues"
Severity Table:        15+27+20+7 = 69
Appendix Categories:   12+14+3+1+14+10+5+8 = 67
Claimed:               "69 verified findings"
```

**All three numbers are mutually inconsistent.**

**Root Causes Identified**:
- Findings added/removed during editing but counts not recalculated
- Multiple sections edited independently by different agent sessions
- No automated count validation before finalization
- Appendix categories manually counted with human error

**Prevention Rule PR-001: Automated Count Validation**
```python
# MUST run before finalizing ANY audit report
def validate_finding_counts(report):
    """
    Validates that all count references in report are consistent.
    Raises AssertionError with details if inconsistent.
    
    Returns: dict with validated counts
    """
    # Source of truth: Detailed finding list
    detailed_count = len(report.detailed_findings)
    
    # Secondary sources that MUST match
    executive_total = report.executive_summary.total_issues
    severity_sum = sum(report.severity_table.values())
    appendix_sum = sum(report.appendix_categories.values())
    
    # Validation checks
    errors = []
    if detailed_count != executive_total:
        errors.append(f"Detailed({detailed_count}) != Executive({executive_total})")
    if executive_total != severity_sum:
        errors.append(f"Executive({executive_total}) != SeveritySum({severity_sum})")
    if severity_sum != appendix_sum:
        errors.append(f"Severity({severity_sum}) != Appendix({appendix_sum})")
    
    if errors:
        raise CountValidationError(
            message="Count inconsistency detected",
            detailed=detailed_count,
            executive=executive_total,
            severity=severity_sum,
            appendix=appendix_sum,
            errors=errors
        )
    
    return {
        "validated": True,
        "count": detailed_count,
        "source_of_truth": "detailed_finding_list"
    }

class CountValidationError(Exception):
    """Raised when audit report counts don't match"""
    pass
```

**Implementation Checklist**:
- [ ] Run `validate_finding_counts()` as pre-delivery gate
- [ ] If fails, use DETAILED list as source of truth
- [ ] Update all other sections to match
- [ ] Document why discrepancy occurred (for learning)

---

#### ❌ ANTI-PATTERN AP-002: "Stale Finding Retention"

**Description**: Including findings that were already fixed or are no longer applicable.

**Real Examples Found**:

| Finding ID | Original Claim | Reality | Who Caught It |
|------------|---------------|---------|---------------|
| DEEP-010 | Production test bypass enabled | Code has `is_production → False` guard | **GPT Reverification** |
| GitHub Actions Pinning | Actions need SHA pinning | Already fixed in commit `f3ffb23...` | **GPT Reverification** |
| SQL Injection C-04 | Directly exploitable | Has whitelist regex `^[A-Za-z0-9_]+$` | **User Manual Verification** |
| XSS in SharedConversationPage | 3rd XSS instance | `formatMessageContent` escapes first | **User Manual Verification** |

**Root Causes**:
- Audit based on cached/outdated code snapshot
- Didn't check git log for recent fixes
- Copied findings from previous audit without re-verification
- Assumed vulnerability presence without checking mitigations

**Prevention Rule PR-002: Staleness Detection System**
```bash
#!/bin/bash
# check_finding_staleness.sh - Run BEFORE claiming any finding
# Usage: ./check_finding_staleness.sh <file_path> <line_number> <claim_description>

FILE_PATH="$1"
LINE_NUMBER="$2"
CLAIM="$3"
COMMIT_HASH=$(git rev-parse HEAD)

echo "=== Staleness Check ==="
echo "Claim: $CLAIM"
echo "File: $FILE_PATH:$LINE_NUMBER"
echo "Current Commit: $COMMIT_HASH"
echo ""

# Check recent changes to this file
echo "--- Recent Changes ---"
git log --oneline -10 -- "$FILE_PATH" 2>/dev/null || echo "No git history"

echo ""
echo "--- Current Content at Line $LINE_NUMBER ---"
sed -n "${LINE_NUMBER}p" "$FILE_PATH" 2>/dev/null || echo "Line not found"

echo ""
echo "--- Git Blame Context ---"
git blame -L "$LINE_NUMBER,$(($LINE_NUMBER + 5))" "$FILE_PATH" 2>/dev/null | head -6

echo ""
echo "--- Surrounding Context (+/- 3 lines) ---"
sed -n "$(($LINE_NUMBER - 3)),$(($LINE_NUMBER + 3))p" "$FILE_PATH"

echo ""
echo "=== Staleness Check Complete ==="
echo "MANUAL REVIEW REQUIRED: Does current code still match claim?"
```

**Validation Checklist for Each Finding**:
- [ ] Check `git log --oneline -10` for recent changes to file
- [ ] Verify line numbers still match current code EXACTLY
- [ ] Run `git blame` to see when vulnerable code was introduced/modified
- [ ] Check for existing mitigations (whitelists, guards, sanitizers)
- [ ] If fixed in later commit → mark STALE (don't delete, keep for history)
- [ ] If partially mitigated → adjust severity/description

---

### Category 2: SEVERITY MISJUDGMENT ERRORS

#### ❌ ANTI-PATTERN AP-003: "P0 Inflation"

**Description**: Labeling moderate issues as P0-CRITICAL, diluting true critical priority.

**Real Severity Corrections**:

| Finding | Original Severity | Corrected Severity | Correction Reason | Source |
|---------|------------------|-------------------|-------------------|--------|
| SEC-004 Firebase Key | P0-CRITICAL | P2/P3-HYGIENE | Firebase keys public by design; has prod guard; value is obviously fake | **GPT + User** |
| CI Test Secret | P0-CREDENTIAL LEAK | P1/P2-RISK | Value contains "test_string"; only risk if copied to production | **GPT** |
| C-04 SQL Injection | P0/P1-EXPLOITABLE | P2-CODE SMELL | Whitelist regex present; table name from information_schema not user input | **User Manual** |
| Memory 88% OOM | P0-OOM IMMINENT | P1-HIGH PRESSURE | 88% ≠ automatic OOM; needs load test evidence on 512MB Render | **GPT** |

**Root Causes of Inflation**:
- Applied generic security rules without domain-specific context
- Didn't consider platform-specific guidance (Firebase official docs)
- Treated all hardcoded strings equally regardless of reachability
- Assumed worst-case exploitability without proof
- Used scary language ("imminent", "bypass") for attention

**Prevention Rule PR-003: Severity Calibration Matrix**
```python
SEVERITY_DECISION_TREE = {
    "hardcoded_secret": {
        "P0_CRITICAL": {
            "conditions": [
                "Reachable in production path (no dev-only guard)",
                "Is REAL credential (not placeholder/fake/test)",
                "Grants privileged access (admin, DB, payment)",
                "No runtime fail-fast if missing",
                "Value looks like real secret (not 'xxx', 'fake', 'test')"
            ],
            "examples": ["production_db_password", "jwt_signing_key_real", "api_key_live"],
            "anti_examples": ["firebase_demo_key", "test_string_placeholder"]
        },
        "P1_HIGH": {
            "conditions": [
                "Reachable in production BUT value is clearly test/fake",
                "Could become real credential if someone copy-pastes",
                "Non-privileged access or limited scope",
                "Has some form of guard but bypassable"
            ],
            "examples": ["dev_default_password", "test_api_key_123"],
            "action": "Remove fallback, add clear comment, add pre-commit hook"
        },
        "P2_MEDIUM": {
            "conditions": [
                "Has explicit production guard (throws Error if PROD)",
                "Platform-specific public-by-design (Firebase API key)",
                "Clearly fake value like 'xxx-change-me' or 'AIzaSyFake'",
                "Only reachable in development mode"
            ],
            "examples": ["firebase_demo_key", "placeholder_token"],
            "action": "Code hygiene cleanup, low priority"
        }
    },
    
    "injection_vulnerability": {
        "P0_EXPLOITABLE": {
            "conditions": [
                "User input reaches dangerous function WITHOUT sanitization",
                "Direct concatenation into SQL/HTML/Command string",
                "No parameterized queries / prepared statements / escaping",
                "Exploit chain is straightforward (no complex prerequisites)"
            ],
            "examples": [f"SELECT * FROM {user_input}", "eval(user_data)"]
        },
        "P1_NEEDS_MITIGATION": {
            "conditions": [
                "User input reaches function WITH partial sanitization",
                "Some protection exists but insufficient or bypassable",
                "Defense-in-depth issue (existing control could fail)"
            ],
            "examples": [
                "SQL with whitelist regex (C-04 case) - protection exists",
                "HTML escape exists but bypassable with specific encoding"
            ],
            "note": "User verified C-04 has whitelist - this is P2 not P0"
        },
        "P2_CODE_QUALITY": {
            "conditions": [
                "Vulnerable pattern exists but input is controlled/server-side",
                "Exploit would require another vulnerability first",
                "Theoretical concern only"
            ]
        }
    },
    
    "memory_performance": {
        "P0_OOM_RISK": {
            "conditions": [
                "Memory usage > 95% of available sustained under load",
                "Load test evidence shows actual crashes/OOM kills",
                "Memory grows unbounded (no GC possible)",
                "Free tier with no scaling option"
            ]
        },
        "P1_HIGH_PRESSURE": {
            "conditions": [
                "Memory usage 75-90% under normal load",
                "Headroom exists but concerning under concurrency",
                "Potential for OOM under spike load (not imminent)",
                "Example: 88% on 512MB Render free tier"
            ],
            "corrected_wording": "Sustained high memory utilization; OOM risk under concurrency/spike load"
        }
    }
}

def calibrate_severity(finding_type, evidence_dict):
    """
    Returns calibrated severity with reasoning.
    Requires evidence_dict with specific fields based on finding_type.
    """
    rules = SEVERITY_DECISION_TREE.get(finding_type, {})
    
    if not rules:
        return "P1_DEFAULT", "Unknown finding type - manual review required"
    
    for severity, criteria in rules.items():
        conditions_met = 0
        total_conditions = len(criteria["conditions"])
        
        for condition_check in criteria["conditions"]:
            # Each condition is a description of what must be true
            # Map these to actual checks on evidence
            if evaluate_condition(condition_check, evidence_dict):
                conditions_met += 1
        
        # Require 80% of conditions to match
        if conditions_met / total_conditions >= 0.8:
            return severity, {
                "reasoning": criteria.get("examples", []),
                "action": criteria.get("action", "Apply standard remediation"),
                "confidence": f"{conditions_met}/{total_conditions} conditions met"
            }
    
    return "P1_DEFAULT", "Does not clearly match any severity level - expert review needed"


# User Verification Lessons (from C-01 to C-05)
USER_VERIFICATION_LESSONS = {
    "C01_INFISICAL_SECRETS": {
        "original_claim": "Hardcoded Infisical secrets in multiple files",
        "user_verification": "100% CONFIRMED",
        "same_secret_found": "316ae8ea...",
        "lesson": "When user confirms 100%, trust it - but note action required (rotate immediately)",
        "process_improvement": "Add secret rotation timeline to finding"
    },
    "C02_XSS_VULNERABILITIES": {
        "original_claim": "3 XSS instances via dangerouslySetInnerHTML",
        "user_verification": "2 OF 3 CONFIRMED (67%)",
        "false_positive_details": {
            "file": "SharedConversationPage.tsx",
            "reason": "formatMessageContent escapes content BEFORE dangerouslySetInnerHTML",
            "lesson": "Check if sanitization happens UPSTREAM, not just at the sink"
        },
        "confirmed_instances": [
            "ArtifactsPanel.tsx (line 208) - raw SVG content",
            "ArtifactsPanel.tsx (lines 230-231) - highlightSyntax() HTML injection",
            "ChatSearchDialog.tsx (lines 111,114) - server highlight content"
        ],
        "process_improvement": "Trace data flow from source to sink, don't just check sink"
    },
    "C03_JWT_LOCALSTORAGE": {
        "original_claim": "~40+ files store JWT in localStorage",
        "user_verification": "CONFIRMED BUT COUNT OVERSTATED",
        "actual_count": "~20-22 files",
        "overstatement_reason": "Counted all localStorage usage, not just JWT tokens",
        "risk_context": "Valid concern IF XSS occurs (and we have 3 confirmed XSS vulns)",
        "process_improvement": "Be precise with counts - grep for specific pattern not broad usage"
    },
    "C04_SQL_INJECTION": {
        "original_claim": "SQL injection vulnerability in admin.py",
        "user_verification": "OVERSTATED - NOT DIRECTLY EXPLOITABLE",
        "mitigation_found": "Whitelist regex validation: ^[A-Za-z0-9_]+$",
        "data_source": "Table name from information_schema, NOT direct user input",
        "correct_classification": "Code smell / defense-in-depth issue only",
        "correct_severity": "P2 (not P0/P1)",
        "process_improvement": "Always check for EXISTING mitigations before claiming exploitability"
    },
    "C05_ERROR_LEAKAGE": {
        "original_claim": "Raw exception messages sent to client",
        "user_verification": "100% CONFIRMED",
        "exact_lines_matched": ["admin.py:52,137,157,399", "server.py:204 (report said 196)"],
        "affected_scope": "~35+ files with similar pattern",
        "lesson": "User confirmed exact line numbers - our line numbers were slightly off",
        "process_improvement": "Double-check line numbers against current HEAD, not cached analysis"
    }
}
```

---

#### ❌ ANTI-PATTERN AP-004: "Wording Precision Failure"

**Description**: Using technically incorrect, exaggerated, or imprecise language.

**Real Wording Corrections Needed**:

| Original Wording | Problem | Corrected Wording | Why It Matters |
|------------------|---------|-------------------|----------------|
| "Authentication Bypass via API Key Fallback" | API key IS valid credential, not a bypass | "Privileged alternate authentication path; system API credential grants admin privileges" | Accuracy matters for remediation decisions |
| "88% memory = OOM imminent" | 88% ≠ automatic OOM; depends on workload, GC, allocator | "Sustained high memory utilization (88%); OOM risk under concurrency on 512MB free tier" | Prevents panic, enables proper prioritization |
| "All endpoints require authentication" | Factually false - public paths exist | "Business endpoints require authentication; public paths exist for docs, health, webhooks" | Factual accuracy is non-negotiable |
| "69 verified findings" | Counts were inconsistent | "~42-58 genuinely supported findings (see count validation)" | Don't defend incorrect numbers |
| "Directly exploitable SQL injection" | Has whitelist mitigation | "SQL construction pattern with existing whitelist validation (defense-in-depth)" | Enables correct prioritization |

**Prevention Rule PR-004: Wording Standards & Blacklist**
```python
WORDING_BLACKLIST = {
    # === Terms requiring EVIDENCE THRESHOLD ===
    "imminent": {
        "required_evidence": "Load test showing crash/OOM/proven exploitation",
        "alternative": "at_risk_under_concurrency" if memory else "potential_risk",
        "example_error": "OOM imminent → OOM risk under load (need load test to confirm imminent)"
    },
    "always": {
        "required_evidence": "Verified ALL code paths, no exceptions",
        "alternative": "typically/in_most_cases",
        "example_error": "Always validates input → Validates input in observed paths"
    },
    "never": {
        "required_evidence": "Formal proof or exhaustive test coverage",
        "alternative": "should_not/expected_not_to",
        "example_error": "Never leaks data → No known leakage paths"
    },
    "bypass": {
        "required_evidence": "Completely circumvents authentication, not alt credential",
        "alternative": "alternate_authentication_path/privileged_credential_path",
        "example_error": "Auth bypass via API key → Admin access via system API key (valid credential)"
    },
    "all": {
        "required_evidence": "Literally 100% coverage verified",
        "alternative": "most/widespread/observed_in",
        "example_error": "All endpoints secured → Business endpoints secured"
    },
    
    # === Security-SPECIFIC precision requirements ===
    "credential leak": {
        "distinction": "Must distinguish: real vs test vs fake vs public-by-design values",
        "firebase_special_case": "Firebase web API keys are PUBLIC BY DESIGN per Google docs",
        "check": "Is this actually a secret or just a configuration value?"
    },
    "injection": {
        "requirement": "Prove exploitability chain, not just presence of string concat",
        "check_mitigations_first": "Whitelist? Parameterized? Escaped? Validated upstream?",
        "c04_lesson": "User found whitelist regex - changed from P0 to P2"
    },
    "vulnerability": {
        "requirement": "Require complete exploit chain, not just code pattern",
        "ask": "Attacker position? Prerequisites? Impact if exploited?"
    }
}

def validate_wording(text, finding_context=None):
    """
    Scans text for blacklisted/imprecise terms.
    Returns list of violations with suggested corrections.
    """
    import re
    
    violations = []
    
    for term, rules in WORDING_BLACKLIST.items():
        pattern = r'\b' + term + r'\b'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            violation = {
                "term": term,
                "position": match.start(),
                "context": text[max(0,match.start()-30):match.end()+30],
                "issue": rules.get("required_evidence", rules.get("distinction", "Review needed")),
                "suggestion": rules.get("alternative", "Provide evidence or reword")
            }
            violations.append(violation)
    
    return violations


# LESSON FROM USER VERIFICATION: Be precise about what was ACTUALLY checked
WORDING_VERIFICATION_STANDARDS = {
    "claim_vs_verification": {
        "rule": "If you write 'verified', specify WHO verified and WHAT they checked",
        "good": "✅ VERIFIED by repo owner via source-level code inspection (lines X-Y confirmed)",
        "bad": "❌ VERIFIED (by whom? how? what exactly?)"
    },
    "count_precision": {
        "rule": "Use ranges or exact counts, not approximations without basis",
        "good": "~20-22 files (grep pattern: localStorage\\.(get|set)Item.*token)",
        "bad": "~40+ files (where did this number come from?)",
        "c03_lesson": "User found actual count was ~20, not ~40 - we double-counted"
    },
    "line_number_accuracy": {
        "rule": "Verify line numbers against CURRENT HEAD, not cached analysis",
        "good": "server.py:204 (verified against commit abc1234)",
        "bad": "server.py:196 (off by 8 lines - likely from earlier version)",
        "c05_lesson": "User confirmed lines but our numbers were slightly off"
    }
}
```

---

### Category 3: DETECTION GAP ERRORS

#### ❌ ANTI-PATTERN AP-005: "Surface-Level Scanning Only"

**Description**: Checking individual files without tracing cross-cutting concerns, architecture, or end-to-end flows.

**Critical Issues Missed by Super Z (Found by GPT)**:

| Issue ID | What Was Missed | Why It Was Missed | Detection Method That Would Have Caught It |
|----------|----------------|-------------------|-------------------------------------------|
| **NEW-001** | Duplicate DB engines (`core/db.py` vs `database/session.py`) | Audited files individually, didn't trace DB lifecycle | L2 Architecture Trace |
| **NEW-002** | Billing duplicate paths + webhook false-success | Didn't follow payment flow end-to-end | L3 Transaction Flow Analysis |
| **NEW-003** | Hardcoded password `supreme-admin-2026-prod` | Config validation files not in security scope | L4 Config Fallback Audit |
| **NEW-004** | Hardcoded ALLOWED_HOSTS with `*.onrender.com` wildcard | Focus on secrets only, not config defaults | L4 Config Fallback Audit |
| **NEW-005** | Stripe `SecretStr` type misuse (direct assignment) | Type annotation checking not in scope | L5 Static Type Analysis |

**Additional Issues That Should Have Been Caught**:
- Comment/code behavior mismatch in cache stubs (GPT found)
- Payment webhook returns success without processing (business logic bug)

**Prevention Rule PR-005: Multi-Layer Detection Strategy (MANDATORY)**
```python
DETECTION_LAYERS = {
    "L1_FILE_PATTERN_SCAN": {
        "what": "Individual file-level patterns (regex, AST, grep)",
        "tools": ["ripgrep", "ast.parse", "semgrep patterns"],
        "catches": ["XSS sinks", "hardcoded strings", "error exposure patterns", "dangerous functions"],
        "misses": ["Cross-file issues", "architecture problems", "runtime behavior", "type misuse"],
        "time_estimate": "Fast (30 min for 2000 files)",
        "examples_caught": "SEC-001 to SEC-003 (XSS), INFRA-001 (CI secrets)"
    },
    
    "L2_ARCHITECTURE_TRACE": {
        "what": "Cross-cutting concerns: duplicate systems, split ownership, circular deps",
        "tools": ["import graph analysis", "dependency tree", "module responsibility mapping"],
        "catches": ["Duplicate DB engines", "Duplicate auth systems", "Duplicate cache layers", "Split session management"],
        "misses_without_this": ["NEW-001 duplicate DB engines", "Architecture inconsistencies"],
        "mandatory_checks": [
            "Are there multiple files defining database engines/connections?",
            "Are there multiple auth middleware implementations?",
            "Are there multiple cache layer implementations?",
            "Do health checks reference the correct canonical subsystem?"
        ],
        "time_estimate": "Medium (2-3 hours for deep trace)"
    },
    
    "L3_TRANSACTION_FLOW_ANALYSIS": {
        "what": "End-to-end request lifecycle for critical paths",
        "tools": ["Request tracer", "call tree generator", "data flow diagrammer"],
        "critical_paths_to_trace": [
            "User signup → email verification → login → JWT issuance",
            "Payment creation → Stripe webhook → wallet credit/subscription activation",
            "API request → auth → rate limit → business logic → response → error handling",
            "Chat message → SSE/WebSocket → storage → retrieval → display"
        ],
        "catches": ["Payment bugs", "auth bypasses", "race conditions", "false-success responses"],
        "misses_without_this": ["NEW-002 billing webhook false-success"],
        "time_estimate": "Slow (4-6 hours for all critical paths)"
    },
    
    "L4_CONFIG_FALLBACK_AUDIT": {
        "what": "ALL configuration defaults, not just secrets",
        "tools": ["Env var tracer", "default value finder", ".env.example scanner"],
        "catches": ["Hardcoded passwords", "wildcard hosts", "fake credentials", "production-inappropriate defaults"],
        "patterns_to_scan": [
            r"password\s*=\s*[\"'][^\"']+[\"']",  # Any hardcoded password
            r"allowed_hosts\s*=\s*",              # Host config
            r"\*\.onrender\.com|\*\.herokuapp\.com",  # Wildcard domains
            r"prod.*password|production.*secret",     # Production secrets
            r"fallback\s*=\s*[\"'][^\"']+"           # Any fallback value
        ],
        "misses_without_this": ["NEW-003 password", "NEW-004 ALLOWED_HOSTS"],
        "time_estimate": "Medium (1-2 hours)"
    },
    
    "L5_STATIC_TYPE_ANALYSIS": {
        "what": "Type correctness, especially for sensitive types",
        "tools": ["mypy", "pyright", "custom type annotation scanner"],
        "sensitive_types_to_check": [
            ("SecretStr", "Must use .get_secret_value(), never assign directly"),
            ("HttpUrl", "Must validate scheme/host"),
            ("DateTime", "Must be timezone-aware in production"),
            ("Bytes", "Check encoding assumptions")
        ],
        "catches": ["SecretStr misuse", "Type confusion", "Missing validation", "Annotation errors"],
        "misses_without_this": ["NEW-005 Stripe SecretStr direct assignment"],
        "time_estimate": "Medium (1-2 hours with type checker setup)"
    }
}

def comprehensive_audit_scan(target_dir, audit_id):
    """
    Runs ALL detection layers and produces unified findings.
    MANDATORY for production-grade audits.
    """
    results = {
        "audit_id": audit_id,
        "timestamp": datetime.now().isoformat(),
        "target": target_dir,
        "layers_run": [],
        "findings_by_layer": {},
        "cross_layer_validation": []
    }
    
    for layer_name, layer_config in DETECTION_LAYERS.items():
        print(f"[{layer_name}] Running: {layer_config['what']}")
        
        layer_result = run_single_layer(layer_name, layer_config, target_dir)
        results["layers_run"].append(layer_name)
        results["findings_by_layer"][layer_name] = layer_result
        
        # Post-layer validation
        if "mandatory_checks" in layer_config:
            for check in layer_config["mandatory_checks"]:
                if not any(check.lower() in str(f).lower() for f in layer_result.get("findings", [])):
                    results["cross_layer_validation"].append({
                        "layer": layer_name,
                        "missing_check": check,
                        "severity": "warning",
                        "message": f"Mandatory check not explicitly addressed: {check}"
                    })
    
    # Cross-layer deduplication
    results["deduplicated_findings"] = deduplicate_findings_across_layers(
        results["findings_by_layer"]
    )
    
    # Quality metrics
    results["quality_metrics"] = {
        "total_layers_run": len(results["layers_run"]),
        "total_findings_raw": sum(len(l.get("findings", [])) for l in results["findings_by_layer"].values()),
        "total_findings_deduplicated": len(results["deduplicated_findings"]),
        "validation_warnings": len(results["cross_layer_validation"]),
        "completeness_score": calculate_completeness_score(results)
    }
    
    return results


# MANDATORY: Production audit must achieve this score
MINIMUM_COMPLETENESS_SCORE = {
    "L1_FILE_SCAN": "REQUIRED - 100%",
    "L2_ARCHITECTURE_TRACE": "REQUIRED - Must find duplicates",
    "L3_FLOW_ANALYSIS": "REQUIRED - For auth, payments, critical paths",
    "L4_CONFIG_AUDIT": "REQUIRED - All fallbacks checked",
    "L5_TYPE_ANALYSIS": "RECOMMENDED - For sensitive types"
}
```

---

### Category 4: CONTEXT INTEGRATION ERRORS

#### ❌ ANTI-PATTERN AP-006: "Ignoring Human/Expert Verification"

**Description**: Not incorporating external verification into final claims, or treating it as optional rather than authoritative.

**How This Manifested**:

| Issue | What Happened | Lesson |
|-------|--------------|--------|
| User verified C-04 SQL injection has whitelist | Report still called it "exploitable" | **User correction should OVERRIDE AI assessment** |
| User found C-03 count was ~20 not ~40 | Report didn't update the count | **Recalculate when given better data** |
| User confirmed exact line numbers for C-05 | Some line numbers still slightly off | **Use user-verified numbers as ground truth** |
| GPT found NEW-001 to NEW-005 | Not incorporated (different audit) | **Cross-audit reconciliation adds value** |

**Prevention Rule PR-006: Verification Integration Protocol**
```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class VerificationStatus(Enum):
    UNVERIFIED = "UNVERIFIED"           # Not yet checked by human/expert
    CONFIRMED = "CONFIRMED"             # Verified correct as stated
    CORRECTED = "CORRECTED"             # Verified but needed adjustment
    REFUTED = "REFUTED"                 # Verified as incorrect/false positive
    PARTIAL = "PARTIAL"                 # Partially correct (specify what %)
    STALE = "STALE"                     # Was true, now fixed

@dataclass
class VerifiedFinding:
    """
    A finding that tracks its own verification state.
    NEVER modify a finding without updating verification metadata.
    """
    id: str
    title: str
    original_severity: str
    file_path: str
    line_numbers: List[int]
    original_claim: str
    evidence_snippet: str
    
    # Verification tracking
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verifications: List[Dict[str, Any]] = field(default_factory=list)
    adjustments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current state (after all adjustments)
    @property
    def current_severity(self) -> str:
        """Returns severity after all corrections"""
        for adj in reversed(self.adjustments):
            if adj.get("field") == "severity":
                return adj["new_value"]
        return self.original_severity
    
    @property
    def current_claim(self) -> str:
        """Returns claim after all corrections"""
        for adj in reversed(self.adjustments):
            if adj.get("field") == "description":
                return adj["new_value"]
        return self.original_claim
    
    def add_verification(
        self,
        verifier: str,                    # "repo_owner", "gpt_audit", "security_team"
        status: VerificationStatus,
        evidence: List[str],              # Lines of evidence provided
        corrections: Optional[List[Dict]] = None,  # Fields to adjust
        notes: Optional[str] = None
    ):
        """
        Add a verification record and auto-adjust finding if corrections provided.
        
        RULE: Human/expert verification OVERRIDES initial AI assessment.
        """
        verification_record = {
            "timestamp": datetime.now().isoformat(),
            "verifier": verifier,
            "status": status.value,
            "evidence": evidence,
            "notes": notes
        }
        
        self.verifications.append(verification_record)
        self.verification_status = status
        
        if corrections:
            for correction in corrections:
                self.adjustments.append({
                    "timestamp": datetime.now().isoformat(),
                    "corrected_by": verifier,
                    "field": correction["field"],         # "severity", "description", "line_numbers"
                    "old_value": self._get_current_field(correction["field"]),
                    "new_value": correction["new_value"],
                    "reason": correction.get("reason", "Per verification feedback")
                })
    
    def _get_current_field(self, field: str) -> str:
        """Get current value of a field after adjustments"""
        if field == "severity":
            return self.current_severity
        elif field == "description":
            return self.current_claim
        elif field == "line_numbers":
            # Return most recently adjusted line numbers
            for adj in reversed(self.adjustments):
                if adj["field"] == "line_numbers":
                    return adj["new_value"]
            return self.line_numbers
        return "[unknown field]"
    
    def is_actionable(self) -> bool:
        """
        Only CONFIRMED and CORRECTED findings should get patches.
        REFUTED/STALE findings should be documented but not patched.
        """
        return self.verification_status in [
            VerificationStatus.CONFIRMED,
            VerificationStatus.CORRECTED
        ]
    
    def get_verification_summary(self) -> Dict:
        """Return summary for report inclusion"""
        return {
            "id": self.id,
            "title": self.title,
            "original_severity": self.original_severity,
            "current_severity": self.current_severity,
            "status": self.verification_status.value,
            "verifier_count": len(self.verifications),
            "adjustment_count": len(self.adjustments),
            "is_actionable": self.is_actionable(),
            "latest_verifier": self.verifications[-1]["verifier"] if self.verifications else None
        }


# EXAMPLE: How user's C-01 to C-05 verification should be recorded
EXAMPLE_VERIFICATION_RECORDS = {
    "C01_INFISICAL_SECRETS": {
        "finding_id": "INFRA-001",
        "verification": {
            "verifier": "repository_owner",
            "status": "CONFIRMED",
            "evidence": [
                "Same secret '316ae8ea...' found in 3 files via grep",
                "Confirmed matches CI workflow, backend config, frontend env"
            ],
            "notes": "100% confirmed - immediate rotation required"
        }
    },
    "C02_XSS_VULNERABILITIES": {
        "finding_id": "SEC-001/002/003",
        "verification": {
            "verifier": "repository_owner",
            "status": "PARTIAL",
            "evidence": [
                "ArtifactsPanel.tsx lines 208, 230-231: CONFIRMED vulnerable",
                "ChatSearchDialog.tsx lines 111,114: CONFIRMED vulnerable",
                "SharedConversationPage.tsx: FALSE POSITIVE - formatMessageContent escapes first"
            ],
            "corrections": [
                {"field": "description", "old_value": "3 XSS instances", "new_value": "2 confirmed XSS instances (1 false positive removed)", "reason": "User traced data flow"}
            ],
            "notes": "2/3 confirmed (67%), 1 false positive due to upstream sanitization"
        }
    },
    "C04_SQL_INJECTION": {
        "finding_id": "SEC-008",
        "verification": {
            "verifier": "repository_owner",
            "status": "CORRECTED",
            "evidence": [
                "Found whitelist regex: ^[A-Za-z0-9_]+$",
                "Table name from information_schema, not direct user input",
                "Not directly exploitable with current controls"
            ],
            "corrections": [
                {"field": "severity", "old_value": "P0/P1", "new_value": "P2", "reason": "Mitigation exists"},
                {"field": "description", "old_value": "SQL injection vulnerability", "new_value": "SQL construction pattern with whitelist validation (defense-in-depth)", "reason": "User verified controls"}
            ],
            "notes": "Overstated initially - defense-in-depth issue only"
        }
    }
}
```

---

## ✅ MANDATORY PRE-DELIVERY VALIDATION CHECKLIST

### Before Finalizing ANY Audit Report (Print and Check Off):

```
═══════════════════════════════════════════════════════════════
          AUDIT PRE-DELIVERY VALIDATION CHECKLIST
          Version: 3.0 (Triple-Source Verified)
═══════════════════════════════════════════════════════════════

□ CATEGORY 1: COUNT CONSISTENCY (AP-001)
  ├─ Executive summary count == Severity table sum?
  ├─ Severity table sum == Appendix category sum?
  └─ All match detailed finding list length?
  │
  └─ If FAIL: Stop. Use detailed list as source of truth. Recalculate others.

□ CATEGORY 2: STALENESS CHECK (AP-002)
  ├─ Each finding's file checked against current HEAD commit?
  ├─ Line numbers verified with sed/cat on current files?
  ├─ Git log reviewed for recent fixes to those lines?
  └─ Existing mitigations checked (whitelists, guards, etc.)?
  │
  └─ If stale found: Mark STALE, don't delete. Note fix commit.

□ CATEGORY 3: SEVERITY CALIBRATION (AP-003)
  ├─ P0 findings: Pass "reachable in production" test?
  ├─ P0 findings: Are REAL credentials (not test/fake)?
  ├─ Platform-specific guidance consulted? (Firebase keys, etc.)
  ├─ Existing mitigations considered? (User lesson: C-04 had whitelist)
  └─ Wording avoids exaggeration? (Not "imminent", "bypass")
  │
  └─ If questionable: Apply calibration matrix, downgrade if needed.

□ CATEGORY 4: WORDING PRECISION (AP-004)
  ├─ No blacklisted terms without evidence? (imminent, always, bypass, all)
  ├─ Technical claims factually accurate?
  ├─ "All/never/always" claims literally true?
  ├─ Verification status precisely described? (Who checked what?)
  └─ Line numbers match current code exactly? (User lesson: C-05 was off)
  │
  └─ If issues found: Rewrite with precise language.

□ CATEGORY 5: DETECTION COMPLETENESS (AP-005)
  ├─ L1 File scan completed? (XSS, secrets, errors)
  ├─ L2 Architecture trace completed? (Duplicate subsystems)
  ├─ L3 Flow analysis for critical paths? (Auth, payments)
  ├─ L4 Config fallback audit? (ALL defaults, not just secrets)
  └─ L5 Type analysis? (SecretStr, Pydantic models)
  │
  └─ If layer skipped: Document gap. May miss critical issues.

□ CATEGORY 6: VERIFICATION INTEGRATION (AP-006)
  ├─ User/human verification received?
  ├─ Findings ADJUSTED based on verification? (Not just appended)
  ├─ Status correctly marked (CONFIRMED/CORRECTED/REFUTED)?
  ├─ Corrections applied to severity/description?
  └─ Actionable list reflects verification status?
  │
  └─ If verification ignored: STOP. Incorporate before delivery.

□ CATEGORY 7: CROSS-AUDIT RECONCILIATION (NEW)
  ├─ If other audit exists, differences listed?
  ├─ Unique findings from OTHER auditor considered?
  └─ Disagreements resolved with evidence?
  │
  └─ If conflicts remain: Present both views, let reader decide.

═══════════════════════════════════════════════════════════════
          QUALITY GATE: Minimum 6/7 categories MUST pass
          Recommended: 7/7 for production audit
═══════════════════════════════════════════════════════════════
```

---

## 📊 ERROR RATE TRACKING METRICS (Updated)

### Track These After Every Audit Cycle:

```python
AUDIT_QUALITY_METRICS = {
    "metrics_version": "3.0",
    
    "count_consistency": {
        "formula": "1 if all_counts_match else 0",
        "target": "100%",
        "super_z_v1": "0%",  # FAILED: 71/69/67 inconsistency
        "lesson_learned": "Automated validation (PR-001) now mandatory"
    },
    
    "false_positive_rate": {
        "formula": "findings_marked_refuted_or_stale / total_findings",
        "target": "< 10%",
        "super_z_v1": "6/42 = 14%",  # Above target
        "false_positives": [
            "DEEP-010 (stale - production guard exists)",
            "GitHub Actions pinning (stale - already fixed)",
            "SharedConversationPage XSS (FP - upstream sanitization)",
            "SEC-004 Firebase (overstated - public by design)"
        ],
        "lesson_learned": "Add staleness detection (PR-002) + upstream tracing"
    },
    
    "severity_accuracy": {
        "formula": "findings_with_correct_severity / total_verified_findings",
        "target": "> 90%",
        "super_z_v1": "~85%",  # SEC-004 wrong, C-04 overstated, memory wording
        "corrections_needed": [
            "SEC-004: P0→P2 (Firebase key public by design)",
            "C-04: P0→P2 (has whitelist mitigation)",
            "Memory: P0→P1 (88% ≠ imminent OOM)"
        ],
        "lesson_learned": "Calibration matrix (PR-003) + domain knowledge required"
    },
    
    "detection_coverage": {
        "formula": "critical_issues_found / total_critical_issues_known",
        "target": "> 95%",
        "super_z_v1": "~90%",  # Missed NEW-001 to NEW-005
        "missed_issues": [
            "NEW-001: Duplicate DB engines (L2 architecture trace needed)",
            "NEW-002: Billing webhook false-success (L3 flow analysis needed)",
            "NEW-003: Hardcoded prod password (L4 config audit needed)",
            "NEW-004: Wildcard ALLOWED_HOSTS (L4 config audit needed)",
            "NEW-005: SecretStr misuse (L5 type analysis needed)"
        ],
        "lesson_learned": "Multi-layer detection (PR-005) now mandatory"
    },
    
    "verification_integration": {
        "formula": "findings_adjusted_based_on_feedback / total_findings_with_feedback",
        "target": "100%",
        "super_z_v1": "~70%",  # Had verification table but didn't fully adjust
        "integration_gaps": [
            "C-04 severity not downgraded after user found whitelist",
            "C-03 count not updated from ~40 to ~20",
            "C-05 line numbers not corrected to user's exact figures"
        ],
        "lesson_learned": "Verification protocol (PR-006) requires AUTO-ADJUSTMENT"
    },
    
    "wording_precision": {
        "formula": "wording_violations / total_claims_made",
        "target": "0%",
        "super_z_v1": "~5%",  # "bypass", "imminent", "all", "69 verified"
        "violations_found": [
            '"Authentication Bypass" should be "Alternate Auth Path"',
            '"OOM imminent" should be "OOM risk under load"',
            '"All endpoints require auth" is factually false',
            '"69 verified" when counts were inconsistent'
        ],
        "lesson_learned": "Wording blacklist (PR-004) + evidence requirements"
    }
}


def calculate_audit_score(audit_results: dict) -> dict:
    """
    Calculate overall audit quality score.
    Must exceed 90% for production delivery.
    """
    scores = {}
    weights = {
        "count_consistency": 15,
        "false_positive_rate": 20,
        "severity_accuracy": 15,
        "detection_coverage": 25,
        "verification_integration": 10,
        "wording_precision": 15
    }
    
    for metric, config in AUDIT_QUALITY_METRICS.items():
        if metric == "metrics_version":
            continue
            
        current_value = audit_results.get(metric, 0)
        target = float(config["target"].rstrip('%'))
        
        # Score as percentage of target
        if target == 100:
            score = current_value * 100  # Already 0-1 scale
        elif target == 0:
            score = 100 if current_value == 0 else (100 - current_value * 1000)
        else:
            score = min(100, (current_value / target) * 100)
        
        scores[metric] = {
            "raw": current_value,
            "target": target,
            "score": score,
            "weight": weights.get(metric, 10),
            "weighted_score": score * weights.get(metric, 10) / 100,
            "lesson": config.get("lesson_learned", "")
        }
    
    total_weighted = sum(s["weighted_score"] for s in scores.values())
    
    return {
        "metric_scores": scores,
        "total_weighted_score": total_weighted,
        "grade": (
            "🟢 PRODUCTION-READY" if total_weighted >= 90 else
            "🟡 ACCEPTABLE" if total_weighted >= 75 else
            "🟠 NEEDS WORK" if total_weighted >= 60 else
            "🔴 UNACCEPTABLE"
        ),
        "recommendation": (
            "Deliver as-is" if total_weighted >= 90 else
            "Minor revisions needed" if total_weighted >= 75 else
            "Significant revision required" if total_weighted >= 60 else
            "Major re-audit required"
        )
    }


# Calculate expected improvement
EXPECTED_IMPROVEMENT = {
    "current_score_v1": "74%",
    "target_score_v2": ">90%",
    "expected_improvements": {
        "count_consistency": "0%→100% (automated validation prevents errors)",
        "false_positive_rate": "14%→<5% (staleness detection + upstream tracing)",
        "severity_accuracy": "85%→>95% (calibration matrix + domain knowledge)",
        "detection_coverage": "90%→>98% (L2-L5 mandatory layers)",
        "verification_integration": "70%→100% (auto-adjustment protocol)",
        "wording_precision": "95%→100% (blacklist enforcement)"
    }
}
```

---

## 🆕 NEW DETECTION RULES (Added After Triple-Source Verification)

### Rule NR-001: Duplicate Subsystem Detection
**Trigger**: Missed NEW-001 (duplicate DB engines)

```python
def detect_duplicate_subsystems(codebase_root: str) -> List[Dict]:
    """
    CRITICAL: Find multiple files implementing SAME responsibility.
    
    Risk: Split ownership causes:
    - Health check inconsistencies
    - Pool config drift  
    - Transaction semantics divergence
    - Test/runtime behavior mismatch
    """
    # Known suspicious patterns (extend based on project structure)
    SUSPICIOUS_DUPLICATES = [
        {
            "subsystem": "database_engine",
            "patterns": ["core/db.py", "database/session.py", "database/connection.py", "db/engine.py"],
            "risk_level": "P0",
            "reason": "DB engine ownership split causes connection pool and health check inconsistencies"
        },
        {
            "subsystem": "authentication",
            "patterns": ["auth/middleware.py", "authentication.py", "security/auth.py", "core/auth.py"],
            "risk_level": "P0",
            "reason": "Multiple auth implementations can have security gaps"
        },
        {
            "subsystem": "cache_layer",
            "patterns": ["core/cache.py", "utils/cache.py", "lib/cache.py", "cache/manager.py"],
            "risk_level": "P1",
            "reason": "Cache inconsistency causes stale data or unnecessary DB hits"
        },
        {
            "subsystem": "payment_processing",
            "patterns": ["billing/api.py", "payments.py", "stripe/webhook.py", "payment/handler.py"],
            "risk_level": "P0",
            "reason": "Payment logic duplication can cause revenue loss or double-charging"
        }
    ]
    
    findings = []
    for suspect in SUSPICIOUS_DUPLICATES:
        existing_files = [
            f for f in suspect["patterns"] 
            if os.path.exists(os.path.join(codebase_root, f))
        ]
        
        if len(existing_files) > 1:
            findings.append({
                "id": f"DUP-{suspect['subsystem'].upper()}",
                "severity": suspect["risk_level"],
                "title": f"Duplicate {suspect['subsystem']} implementation detected",
                "files": existing_files,
                "risk": suspect["reason"],
                "recommendation": f"Consolidate to single canonical {suspect['subsystem']} module",
                "detection_method": "L2_ARCHITECTURE_TRACE"
            })
    
    return findings
```

### Rule NR-002: Config Fallback Chain Auditor
**Trigger**: Missed NEW-003 (hardcoded password), NEW-004 (wildcard hosts)

```python
def audit_config_fallbacks(config_dir: str, include_env_examples: bool = True) -> List[Dict]:
    """
    Find ALL fallback/default values in configuration.
    Not just secrets - hosts, URLs, passwords, feature flags, timeouts.
    
    CRITICAL for: "zero-hardcoded-value / Infisical only" principle compliance
    """
    DANGEROUS_DEFAULT_PATTERNS = [
        {
            "pattern": r"""password\s*=\s*["'][^"']+["']""",
            "name": "hardcoded_password",
            "severity": "P0",
            "special_cases": [
                (r"prod.*password|production.*password", "P0-CRITICAL: Production password"),
                (r"test.*password|dev.*password", "P1: Test password"),
                (r"supreme-admin-\d{4}-\w+", "P0: Named production password (NEW-003 pattern)")
            ]
        },
        {
            "pattern": r"""allowed_hosts\s*=\s*[\[\(]["'][^"']+["']""",
            "name": "allowed_hosts_config",
            "severity": "P1",
            "special_cases": [
                (r"\*\.\w+", "P1: Wildcard host pattern (NEW-004 pattern)"),
                (r"onrender\.com|herokuapp\.com|vercel\.app", "P1: Broad platform trust boundary")
            ]
        },
        {
            "pattern": r"""fallback\s*=\s*["'][^"']+["']""",
            "name": "generic_fallback",
            "severity": "P2",
            "note": "Any fallback value could become production default"
        },
        {
            "pattern": r"""(apiKey|api_key|secret)\s*=\s*["'](AIzaSy|fake|test|xxx|change)["']""",
            "name": "obviously_fake_credential",
            "severity": "P2/P3",
            "note": "Fake value but check if production-guarded (SEC-004 lesson)"
        }
    ]
    
    findings = []
    
    # Scan Python config files
    for py_file in glob.glob(os.path.join(config_dir, "**/*.py"), recursive=True):
        content = read_file(py_file)
        for rule in DANGEROUS_DEFAULT_PATTERNS:
            for match in re.finditer(rule["pattern"], content, re.IGNORECASE):
                line_num = content[:match.start()].count('\n') + 1
                
                # Check special cases
                for special_pattern, special_rule in rule.get("special_cases", []):
                    if re.search(special_pattern, match.group(), re.IGNORECASE):
                        findings.append({
                            "id": f"CONFIG-{len(findings)+1:03d}",
                            "severity": special_rule.split(":")[0],
                            "title": special_rule.split(":")[1] if ":" in special_rule else rule["name"],
                            "file": py_file,
                            "line": line_num,
                            "matched_text": match.group(),
                            "pattern_type": rule["name"],
                            "recommendation": "Move to Infisical/env var with no fallback",
                            "detection_method": "L4_CONFIG_AUDIT"
                        })
                        break
    
    return findings
```

### Rule NR-003: Pydantic SecretStr Misuse Scanner
**Trigger**: Missed NEW-005 (Stripe key assigned without .get_secret_value())

```python
def scan_secretstr_misuse(python_files: List[str]) -> List[Dict]:
    """
    Find where SecretStr values used without .get_secret_value().
    
    RISK: Direct assignment leaks secret in:
    - Log files (if object is logged)
    - Stack traces (on error)
    - Debug output
    - String serialization
    """
    findings = []
    
    for file_path in python_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Look for assignments like: x.secret = settings.secret_value
                # Where RHS is attribute access that might be SecretStr
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute):
                            # Check if assigning a SecretStr-like attribute
                            if isinstance(node.value, ast.Attribute):
                                attr_name = node.value.attr
                                
                                # Suspicious: Assigning something that looks like secret
                                # WITHOUT calling .get_secret_value()
                                secret_indicators = ['secret', 'key', 'token', 'password', 'api_key']
                                if any(indicator in attr_name.lower() for indicator in secret_indicators):
                                    # Check if there's a .get_secret_value() call somewhere in chain
                                    source_code = ast.unparse(node.value) if hasattr(ast, 'unparse') else content[node.value.col_offset:]
                                    
                                    if 'get_secret_value' not in source_code:
                                        findings.append({
                                            "id": f"TYPE-{len(findings)+1:03d}",
                                            "severity": "P1",
                                            "title": f"Potential SecretStr misuse at line {node.lineno}",
                                            "file": file_path,
                                            "line": node.lineno,
                                            "code_snippet": source_code[:100],
                                            "issue": "SecretStr assigned without .get_secret_value() - may leak in logs/stack traces",
                                            "recommendation": f"Use {attr_name}.get_secret_value() before assignment",
                                            "detection_method": "L5_TYPE_ANALYSIS"
                                        })
        
        except SyntaxError:
            continue  # Skip files with syntax errors
    
    return findings
```

### Rule NR-004: Webhook Safety Analyzer
**Trigger**: Missed NEW-002 (billing webhook returns success without processing)

```python
def analyze_webhook_safety(endpoint_files: List[str]) -> List[Dict]:
    """
    Analyze webhook endpoints for safety issues.
    
    CRITICAL FINDING (NEW-002): Webhook returns HTTP 200/success
    but does NOT actually process the payment (wallet credit, subscription activation).
    
    RISK: If Stripe dashboard misconfigured to point here:
    - Customer pays → Webhook receives → Returns 200 OK
    - But: No wallet credit, no subscription activation
    - Result: Silent payment failure, angry customers, revenue loss
    """
    safety_checks = {
        "signature_verification": {
            "pattern": r"(verify_signature|verify_webhook_signature|construct_event|webhook_signature)",
            "required": True,
            "severity_if_missing": "P0"
        },
        "idempotency_handling": {
            "pattern": r"(idempotency_key|processed_events|deduplicate|already_processed)",
            "required": True,
            "severity_if_missing": "P1"
        },
        "actual_processing": {
            # These indicate REAL processing happens
            "pattern": r"(wallet\.credit|subscription\.activate|order\.confirm|payment\.complete|balance\.update)",
            "required": True,
            "severity_if_missing": "P0"  # THIS CAUGHT NEW-002
        }
    }
    
    findings = []
    
    for file_path in endpoint_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Identify webhook handlers
            if '/webhook' in content.lower() or 'webhook_handler' in content.lower():
                
                # Check each safety requirement
                missing_checks = []
                for check_name, check_config in safety_checks.items():
                    if not re.search(check_config["pattern"], content, re.IGNORECASE):
                        missing_checks.append({
                            "check": check_name,
                            "severity": check_config["severity_if_missing"]
                        })
                
                # CRITICAL CHECK: Does it return success without processing?
                has_success_response = bool(re.search(
                    r'(return.*200|return.*success|JSONResponse.*status.*200)',
                    content, re.IGNORECASE
                ))
                
                processes_payment = bool(re.search(
                    safety_checks["actual_processing"]["pattern"],
                    content, re.IGNORECASE
                ))
                
                if has_success_response and not processes_payment:
                    findings.append({
                        "id": "WEBHOOK-001",
                        "severity": "P0",
                        "title": "Webhook returns success without processing payment",
                        "file": file_path,
                        "risk": "Silent payment failure if Stripe points to this endpoint",
                        "missing_checks": missing_checks,
                        "recommendation": "Add actual payment processing OR remove success response",
                        "detection_method": "L3_FLOW_ANALYSIS",
                        "business_impact": "Revenue loss, customer payment disputes, chargebacks"
                    })
                elif missing_checks:
                    findings.append({
                        "id": f"WEBHOOK-{len(findings)+1:002d}",
                        "severity": max(m["severity"] for m in missing_checks),
                        "title": f"Webhook missing safety checks: {[m['check'] for m in missing_checks]}",
                        "file": file_path,
                        "missing_checks": missing_checks,
                        "detection_method": "L3_FLOW_ANALYSIS"
                    })
        
        except Exception:
            continue
    
    return findings
```

---

## 📋 AUDIT REPORT TEMPLATE (Error-Resistant, Version 3.0)

```markdown
# [PROJECT NAME] PRODUCTION AUDIT REPORT v[X]

## Meta-Data (AUTO-GENERATED - DO NOT EDIT MANUALLY)
| Field | Value |
|-------|-------|
| **Audit ID** | [UUID v4] |
| **Commit Audited** | [Full SHA from git rev-parse HEAD] |
| **Branch** | [git branch --show-current] |
| **Timestamp** | [ISO 8601 UTC] |
| **Auditor** | [AI/Human name + version] |
| **Methodology** | AI_AGENT_ANTIPATTERN_PLAYBOOK.md v3.0 |
| **Playbook Version** | [Version from playbook file] |

---

## ⚠️ COUNT VALIDATION BLOCK (AUTO-CALCULATED - DO NOT EDIT)

| Source | Count | Status |
|--------|-------|--------|
| Detailed Findings List | [auto-count from list] | ✅ SOURCE OF TRUTH |
| Severity Breakdown (P0+P1+P2+P3) | [auto-sum] | ⚠️ Must match above |
| Category Breakdown | [auto-sum] | ⚠️ Must match above |
| Executive Summary Total | [number] | ⚠️ Must match above |

**VALIDATION STATUS**: [✅ PASS / ❌ FAIL - see discrepancies below]

⚠️ **IF COUNTS DON'T MATCH: STOP. Fix before delivering. Do not hand-wave.**

---

## Executive Summary

### Production Readiness Score: [X]% — [GO/NO-GO]

| Metric | Score | Status |
|--------|-------|--------|
| Security Posture | XX/100 | |
| Infrastructure Readiness | XX/100 | |
| Code Quality | XX/100 | |
| Test Coverage | XX/100 | |
| Documentation | XX/100 | |
| **Overall** | **XX/100** | **🟢 GO / 🟠 CONDITIONAL / 🔴 NO-GO** |

---

## Findings (Each With Verification Status)

### [ID]: [Title]
- **Status**: [UNVERIFIED | ✅ CONFIRMED | ✅ CORRECTED | ❌ REFUTED | ⚠️ STALE]
- **Original Severity**: [P0-P3]
- **Current Severity**: [After corrections, if any]
- **File**: [path:line] (Verified against commit [SHA])
- **Evidence**: [Exact code snippet from current HEAD]
- **Exploitability**: [Proven | Theoretical | Needs Penetration Test | Mitigated]
- **Mitigations Found**: [List any existing controls]
- **Verifier Notes**: [What human/expert said about this finding]
- **Patch**: [Link or embedded patch code]

---

## Verification Summary (MANDATORY SECTION)

### Internal Verification (AI Self-Check)
- [ ] Count validation passed
- [ ] Staleness check completed
- [ ] Severity calibration applied
- [ ] Wording review completed

### External Verification (Human/Expert)
| Verifier | Date | Findings Reviewed | Confirmed | Corrected | Refuted |
|----------|------|-------------------|-----------|-----------|---------|
| [Name/Role] | [Date] | [N] | [N] | [N] | [N] |

### Key Adjustments Made Based on Verification
| Finding | Original Claim | Adjustment | Reason |
|---------|---------------|------------|--------|
| [ID] | [What we said] | [What we changed to] | [Why] |

---

## Known Limitations (MANDATORY - HONESTY SECTION)

### What Was NOT Scanned
- [List scopes explicitly excluded]

### Assumptions Made
- [List assumptions with rationale]

### Dependencies on External Verification
- [What needs human confirmation]

### Confidence Level Per Category
| Category | Confidence | Reason |
|----------|------------|--------|
| Security | High/Medium/Low | [Why] |
| Infrastructure | High/Medium/Low | [Why] |
| Performance | High/Medium/Low | [Why] |

---

## Cross-Audit Reconciliation (If Applicable)

### Other Audits Reviewed
| Audit Source | Date | Key Agreements | Key Disagreements |
|--------------|------|----------------|-------------------|
| [Source] | [Date] | [List] | [List] |

### Resolution of Disagreements
| Issue | Our Position | Their Position | Final Decision | Evidence Basis |
|-------|-------------|----------------|----------------|----------------|

---

## Delivery Contents

| Item | Location | Description |
|------|----------|-------------|
| Report | [path] | This document |
| Machine-Readable Summary | [path] | JSON with all findings |
| Patch Guide | [path] | Step-by-step application order |
| Patches | [directory] | Individual fix files |

---

## Quality Metrics (Self-Assessment)

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Count Consistency | 100% | [X]% | |
| False Positive Rate | <10% | [X]% | |
| Severity Accuracy | >90% | [X]% | |
| Detection Coverage | >95% | [X]% | |
| Verification Integration | 100% | [X]% | |
| Wording Precision | 100% | [X]% | |
| **Weighted Total** | **>90%** | **[X]%** | |

---

*Report generated using AI_AGENT_ANTIPATTERN_PLAYBOOK.md v3.0*
*Next playbook review: After next audit cycle or when new error pattern discovered*
```

---

## 🔄 CONTINUOUS IMPROVEMENT PROCESS

### Update Triggers (When to Edit This Playbook):

| Trigger Type | Action | Examples From This Cycle |
|--------------|--------|--------------------------|
| **New False Positive** | Add to AP-002, improve detection | DEEP-010 stale, SharedConversationPage FP |
| **Severity Disagreement** | Add to PR-003 matrix | SEC-004 Firebase, C-04 SQL injection |
| **Critical Issue Missed** | Add to L2-L5 scans | NEW-001 through NEW-005 |
| **Count Error Caught** | Strengthen PR-001 automation | 71/69/67 inconsistency |
| **Wording Criticism** | Expand PR-004 blacklist | "Bypass", "Imminent", "All endpoints" |
| **Verification Ignored** | Strengthen PR-006 protocol | User corrections not applied |
| **New Auditor Feedback** | Add to cross-audit section | GPT found 5 issues we missed |

### Version History

| Version | Date | Changes | Trigger Event |
|---------|------|---------|---------------|
| 1.0 | 2026-01-25 | Initial creation | First audit cycle |
| 2.0 | 2026-01-26 | Added dual-audit lessons (Super Z + GPT) | Count inconsistency, missed issues |
| **3.0** | **2026-01-26** | **TRIPLE-SOURCE: Added user manual verification lessons** | **C-01 to C-05 detailed analysis** |
| | | **Added AP-006 verification integration protocol** | **User corrections not being applied** |
| | | **Expanded PR-003 with user verification examples** | **C-04 severity correction** |
| | | **Added NR-001 to NR-004 detection rules** | **NEW-001 to NEW-005 misses** |
| | | **Added quality metrics tracking** | **Need objective measurement** |
| | | **Added error-resistant report template** | **Prevent future inconsistencies** |

---

## 📚 References

| Document | Purpose |
|----------|---------|
| `PRODUCTION_READINESS_PLAN_V3.md` | Overall readiness tracking |
| `security/SUPREME_SECURITY_GOVERNANCE.md` | Security standards |
| `OWASP_COMPLIANCE_CHECKLIST.md` | Security checklist |
| `CONVENTIONS.md` | Code style guide |
| **This Playbook** | **Audit quality assurance (this document)** |

---

## 🎯 KEY TAKEAWAYS (For Quick Reference)

### The 6 Anti-Patterns to Avoid:
1. **AP-001**: Don't report inconsistent counts (validate automatically)
2. **AP-002**: Don't include stale findings (check git history)
3. **AP-003**: Don't inflate severity (use calibration matrix)
4. **AP-004**: Don't use imprecise wording (evidence-required terms)
5. **AP-005**: Don't only do surface scans (use L1-L5 layers)
6. **AP-006**: Don't ignore verification (auto-adjust findings)

### The 5 Detection Layers (All Mandatory):
- **L1**: File pattern scan (fast, catches obvious issues)
- **L2**: Architecture trace (catches duplicates like NEW-001)
- **L3**: Flow analysis (catches logic bugs like NEW-002)
- **L4**: Config audit (catches hardcoded values like NEW-003/004)
- **L5**: Type analysis (catches type misuse like NEW-005)

### The Golden Rules:
> **Rule 1**: "Counts must match, or don't deliver"  
> **Rule 2**: "Human verification overrides AI assessment"  
> **Rule 3**: "If GPT finds something you missed, YOUR process failed, not theirs"  
> **Rule 4**: "Document limitations honestly - readers respect transparency"  
> **Rule 5**: "Update this playbook after EVERY error discovered"

---

**Remember**: 
> "The goal is not zero errors — it's making DIFFERENT errors each time, then eliminating those too."

**Next Review**: After next audit cycle or when new error pattern discovered  
**Maintainer**: Principal Autonomous Architect (Super Z)  
**Contributors**: Repository Owner (Manual Verification), GPT (Independent Reverification)
