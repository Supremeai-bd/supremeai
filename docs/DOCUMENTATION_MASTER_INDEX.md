# SupremeAI — Master Documentation Inventory & Index

This document provides a comprehensive, centralized index of all documentation, specification, and operational markdown (`.md`) files in the SupremeAI repository.

**Total Document Files Tracked:** `120`  
**Generated Date:** `2026-09-12`  

---

## Table of Contents & Category Summary

| Category / Section | File Count |
| :--- | :--- |
| [.agents](#.agents) | 8 |
| [.clinerules](#.clinerules) | 10 |
| [.github](#.github) | 5 |
| [.lingma](#.lingma) | 1 |
| [.specify](#.specify) | 6 |
| [Root Documents](#root-documents) | 11 |
| [agent-ctx](#agent-ctx) | 1 |
| [apps](#apps) | 5 |
| [audit_reports](#audit_reports) | 3 |
| [backend](#backend) | 15 |
| [docs (Root)](#docs-root) | 1 |
| [docs/master_docs](#docsmaster_docs) | 14 |
| [frontend](#frontend) | 5 |
| [infrastructure](#infrastructure) | 1 |
| [reports](#reports) | 2 |
| [scripts](#scripts) | 4 |
| [specs](#specs) | 15 |
| [tools](#tools) | 13 |

---

## .agents

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 1 | [`.agents/100+rules_for_agent.md`](file:///f:/supremeai/.agents/100+rules_for_agent.md) | **📜 The SupremeAI Elite Developer Manifesto** | বস, আপনার এই মাইন্ডসেটটাই একজন সাধারণ প্রোগ্রামারকে একজন **"Tech Lead"** বা **"Chief Architect"** থেকে আলাদা করে! নতুন ডেভেলপারদের অনবোর্ডিংয়ের জন্য একটি সলি... |
| 2 | [`.agents/rules/AI_AGENT_ANTIPATTERN_PLAYBOOK.md`](file:///f:/supremeai/.agents/rules/AI_AGENT_ANTIPATTERN_PLAYBOOK.md) | **🛡️ AI Agent Coding Anti-Pattern Playbook** | 1. [ভাগ ১: আমাদের আসল ভুলগুলো (Self-Inflicted)](#ভাগ-১-আমাদের-আসল-ভুলগুলো) |
| 3 | [`.agents/skills/browser-automation/SKILL.md`](file:///f:/supremeai/.agents/skills/browser-automation/SKILL.md) | **Browser Automation** | Browser automation powers web testing, scraping, and AI agent |
| 4 | [`.agents/skills/concise-planning/SKILL.md`](file:///f:/supremeai/.agents/skills/concise-planning/SKILL.md) | **Concise Planning** | Use when a user asks for a plan for a coding task, to generate a clear, actionable, and atomic checklist. |
| 5 | [`.agents/skills/environment-health/SKILL.md`](file:///f:/supremeai/.agents/skills/environment-health/SKILL.md) | **Environment Health Check** | Check the operational status of SupremeAI environments and external dependencies (Render, Supabase, Infisical, Cloudflare, GitHub, etc.). |
| 6 | [`.agents/skills/fastapi-pro/SKILL.md`](file:///f:/supremeai/.agents/skills/fastapi-pro/SKILL.md) | **Use this skill when** | Build high-performance async APIs with FastAPI, SQLAlchemy 2.0, and Pydantic V2. Master microservices, WebSockets, and modern Python async patterns. |
| 7 | [`.agents/skills/github-actions-debugger/SKILL.md`](file:///f:/supremeai/.agents/skills/github-actions-debugger/SKILL.md) | **GitHub Actions Pipeline Debugger** | Specialized skill for diagnosing, analyzing, and fixing failing GitHub Actions workflows by parsing run logs and pipeline definitions. |
| 8 | [`.agents/skills/mcp-tool-developer/SKILL.md`](file:///f:/supremeai/.agents/skills/mcp-tool-developer/SKILL.md) | **MCP Tool Developer** | Build Model Context Protocol (MCP) servers and tools from scratch. Full-stack MCP development with TypeScript/Python, testing, deployment, and registry publi... |

## .clinerules

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 9 | [`.clinerules/workflows/speckit-analyze.md`](file:///f:/supremeai/.clinerules/workflows/speckit-analyze.md) | **User Input** | Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation. |
| 10 | [`.clinerules/workflows/speckit-checklist.md`](file:///f:/supremeai/.clinerules/workflows/speckit-checklist.md) | **Checklist Purpose: "Unit Tests for English"** | Generate a custom checklist for the current feature based on user requirements. |
| 11 | [`.clinerules/workflows/speckit-clarify.md`](file:///f:/supremeai/.clinerules/workflows/speckit-clarify.md) | **User Input** | Identify underspecified areas in the current feature spec by asking up to 5 highly targeted clarification questions and encoding answers back into the spec. |
| 12 | [`.clinerules/workflows/speckit-constitution.md`](file:///f:/supremeai/.clinerules/workflows/speckit-constitution.md) | **User Input** | Create or update the project constitution from interactive or provided principle inputs. |
| 13 | [`.clinerules/workflows/speckit-converge.md`](file:///f:/supremeai/.clinerules/workflows/speckit-converge.md) | **User Input** | Assess the current codebase against the feature's spec, plan, and tasks, then append any remaining unbuilt work as new tasks to tasks.md so implement can com... |
| 14 | [`.clinerules/workflows/speckit-implement.md`](file:///f:/supremeai/.clinerules/workflows/speckit-implement.md) | **User Input** | Execute the implementation plan by processing and executing all tasks defined in tasks.md |
| 15 | [`.clinerules/workflows/speckit-plan.md`](file:///f:/supremeai/.clinerules/workflows/speckit-plan.md) | **User Input** | Execute the implementation planning workflow using the plan template to generate design artifacts. |
| 16 | [`.clinerules/workflows/speckit-specify.md`](file:///f:/supremeai/.clinerules/workflows/speckit-specify.md) | **User Input** | Create or update the feature specification from a natural language feature description. |
| 17 | [`.clinerules/workflows/speckit-tasks.md`](file:///f:/supremeai/.clinerules/workflows/speckit-tasks.md) | **User Input** | Generate an actionable, dependency-ordered tasks.md for the feature based on available design artifacts. |
| 18 | [`.clinerules/workflows/speckit-taskstoissues.md`](file:///f:/supremeai/.clinerules/workflows/speckit-taskstoissues.md) | **User Input** | Convert existing tasks into actionable, dependency-ordered GitHub issues for the feature based on available design artifacts. |

## .github

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 19 | [`.github/actions/setup-backend/failed_job_log.md`](file:///f:/supremeai/.github/actions/setup-backend/failed_job_log.md) | **failed_job_log.md** | TOTAL                                              13257   4428   3204    531    64% |
| 20 | [`.github/scripts/maintenance-pipeline-documentation-bn.md`](file:///f:/supremeai/.github/scripts/maintenance-pipeline-documentation-bn.md) | **📖 রক্ষণাবেক্ষণ এবং অটো-ফিক্স ওয়ার্কফ্লো (`maintenance_pipeline.yml`)** | এই ডকুমেন্টটি আমাদের `maintenance_pipeline.yml` ওয়ার্কফ্লোর কার্যকারিতা, বিভিন্ন ধাপ এবং এর পেছনের মূল ধারণাগুলো ব্যাখ্যা করে। এই পাইপলাইনটি আমাদের CI সিস্টে... |
| 21 | [`.github/scripts/supreme-ci-auto-fix-documentation-bn.md`](file:///f:/supremeai/.github/scripts/supreme-ci-auto-fix-documentation-bn.md) | **📖 স্বয়ংক্রিয় মেরামতকারী ওয়ার্কফ্লো (`supreme-ci-auto-fix.yml`)** | এই ডকুমেন্টটি আমাদের `supreme-ci-auto-fix.yml` ওয়ার্কফ্লোর কার্যকারিতা, বিভিন্ন ধাপ এবং এর পেছনের মূল ধারণাগুলো ব্যাখ্যা করে। এই পাইপলাইনটি আমাদের CI সিস্টেম... |
| 22 | [`.github/scripts/supreme-ci-documentation-bn.md`](file:///f:/supremeai/.github/scripts/supreme-ci-documentation-bn.md) | **📖 SupremeAI Smart CI/CD ওয়ার্কফ্লো (`supreme-ci.yml`)** | এই ডকুমেন্টটি আমাদের প্রধান CI/CD (Continuous Integration/Continuous Deployment) পাইপলাইন `supreme-ci.yml`-এর কার্যকারিতা, বিভিন্ন ধাপ এবং এর পেছনের মূল ধারণ... |
| 23 | [`.github/scripts/supreme-release-builds-documentation-bn.md`](file:///f:/supremeai/.github/scripts/supreme-release-builds-documentation-bn.md) | **📖 রিলিজ বিল্ড ওয়ার্কফ্লো (`supreme-release-builds.yml`)** | এই ডকুমেন্টটি আমাদের `supreme-release-builds.yml` ওয়ার্কফ্লোর কার্যকারিতা, বিভিন্ন ধাপ এবং এর পেছনের মূল ধারণাগুলো ব্যাখ্যা করে। এই পাইপলাইনটি আমাদের সফটওয়্য... |

## .lingma

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 24 | [`.lingma/rules/agents.md`](file:///f:/supremeai/.lingma/rules/agents.md) | **SupremeAI Agent Core Directives (Self-Evolving Phase)** | trigger: always_on |

## .specify

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 25 | [`.specify/memory/constitution.md`](file:///f:/supremeai/.specify/memory/constitution.md) | **SupremeAI Engineering Constitution** | Spec-Driven Development (SDD) principles for the SupremeAI platform. |
| 26 | [`.specify/templates/checklist-template.md`](file:///f:/supremeai/.specify/templates/checklist-template.md) | **[CHECKLIST TYPE] Checklist: [FEATURE NAME]** | ============================================================================ |
| 27 | [`.specify/templates/constitution-template.md`](file:///f:/supremeai/.specify/templates/constitution-template.md) | **[PROJECT_NAME] Constitution** | <!-- Example: Spec Constitution, TaskFlow Constitution, etc. --> |
| 28 | [`.specify/templates/plan-template.md`](file:///f:/supremeai/.specify/templates/plan-template.md) | **Implementation Plan: [FEATURE]** | [Extract from feature spec: primary requirement + technical approach from research] |
| 29 | [`.specify/templates/spec-template.md`](file:///f:/supremeai/.specify/templates/spec-template.md) | **Feature Specification: [FEATURE NAME]** | $ARGUMENTS |
| 30 | [`.specify/templates/tasks-template.md`](file:///f:/supremeai/.specify/templates/tasks-template.md) | **Tasks: [FEATURE NAME]** | Task list template for feature implementation |

## Root Documents

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 31 | [`AGENTS.md`](file:///f:/supremeai/AGENTS.md) | **SupremeAI Agent Configuration Guide** | This document defines the configuration, behavior, and operational guidelines for all AI agents in the SupremeAI platform. |
| 32 | [`AUDIT_REPORT_2026-09-10.md`](file:///f:/supremeai/AUDIT_REPORT_2026-09-10.md) | **SupremeAI — Full Git-Tracked Repository Audit Report** | This report is the result of a full-codebase health check on the git-tracked tree: lint, type-check, test collection, dead-code analysis, secret scanning, an... |
| 33 | [`CHECKPOINT.md`](file:///f:/supremeai/CHECKPOINT.md) | **SupremeAI Session Checkpoint** | System documentation and operational guidance file. |
| 34 | [`CI_PIPELINE_OPTIMIZATION_ANALYSIS.md`](file:///f:/supremeai/CI_PIPELINE_OPTIMIZATION_ANALYSIS.md) | **SupremeAI CI/CD Pipeline Optimization Analysis** | Your pipeline consists of **6 workflows** with **40+ jobs** running across push, PR, schedule, and manual triggers. Current issues: |
| 35 | [`CONTRIBUTING.md`](file:///f:/supremeai/CONTRIBUTING.md) | **Contributing to SupremeAI** | Thank you for your interest in contributing to SupremeAI! This document provides guidelines and instructions for contributing to the project. |
| 36 | [`LESSONS_LEARNED.md`](file:///f:/supremeai/LESSONS_LEARNED.md) | **LESSONS_LEARNED** | System documentation and operational guidance file. |
| 37 | [`MODULES_LIST.md`](file:///f:/supremeai/MODULES_LIST.md) | **SupremeAI - Comprehensive List of Modules** | Total Modules: **194** |
| 38 | [`PRODUCTION_ROADMAP_2026-09-11.md`](file:///f:/supremeai/PRODUCTION_ROADMAP_2026-09-11.md) | **SupremeAI — প্রোডাকশন রোডম্যাপ (২০২৬-০৯-১১)** | System documentation and operational guidance file. |
| 39 | [`README.md`](file:///f:/supremeai/README.md) | **SupremeAI 🚀** | <p align="center"><strong>Autonomously Orchestrated AI Task-Execution Platform</strong></p> |
| 40 | [`STATUS.md`](file:///f:/supremeai/STATUS.md) | **SupremeAI System Status (Single Source of Truth)** | System documentation and operational guidance file. |
| 41 | [`admin_tadak.md`](file:///f:/supremeai/admin_tadak.md) | **SupremeAI Manual Administration Tasks** | Please refer to [`docs/ADMIN_TASKS/manual-approvals-bn.md`](docs/ADMIN_TASKS/manual-approvals-bn.md) for the active manual administration tasks. |

## agent-ctx

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 42 | [`agent-ctx/s7-s12-backend-routes.md`](file:///f:/supremeai/agent-ctx/s7-s12-backend-routes.md) | **Work Record: S7–S12 Backend Route Files** | All 6 files pass `py_compile` syntax validation. |

## apps

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 43 | [`apps/docs/docs/api-reference.md`](file:///f:/supremeai/apps/docs/docs/api-reference.md) | **SupremeAI 2.0 — API Reference** | All admin endpoints require JWT Bearer token: |
| 44 | [`apps/docs/docs/bangla-guide.md`](file:///f:/supremeai/apps/docs/docs/bangla-guide.md) | **SupremeAI 2.0 — সম্পূর্ণ গাইড (বাংলা)** | SupremeAI 2.0 হলো একটি **মাল্টি-ক্লাউড AI অর্কেস্ট্রেশন প্ল্যাটফর্ম** যা: |
| 45 | [`apps/docs/docs/elai-code-extension-reference-bn.md`](file:///f:/supremeai/apps/docs/docs/elai-code-extension-reference-bn.md) | **ই-লাই কোড এক্সটেনশন বিশ্লেষণ (eLai Code Extension Analysis)** | ই-লাই কোড (eLai Code) এক্সটেনশনটি একটি পূর্ণাঙ্গ ভিএসকোড (VSCode) এক্সটেনশন যা বিভিন্ন ফিচারের মাধ্যমে ডেভেলপারদের প্রোডাক্টিভিটি বাড়াতে ডিজাইন করা হয়েছে। এট... |
| 46 | [`apps/docs/docs/elai-code-extension-reference.md`](file:///f:/supremeai/apps/docs/docs/elai-code-extension-reference.md) | **eLai Code Extension Analysis** | The eLai Code extension is a comprehensive VSCode extension designed to enhance developer productivity through various features. It appears to be developed b... |
| 47 | [`apps/docs/docs/intro.md`](file:///f:/supremeai/apps/docs/docs/intro.md) | **SupremeAI 2.0 — Getting Started** | Welcome to **SupremeAI 2.0** — a multi-cloud AI orchestration platform that aggregates 8+ AI providers, routes tasks intelligently, and maximizes free-tier u... |

## audit_reports

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 48 | [`audit_reports/supreme-deep-audit-reports/AUDIT_MASTER_CHECKLIST.md`](file:///f:/supremeai/audit_reports/supreme-deep-audit-reports/AUDIT_MASTER_CHECKLIST.md) | **AUDIT_MASTER_CHECKLIST.md** | System documentation and operational guidance file. |
| 49 | [`audit_reports/supreme-deep-audit-reports/FEATURE_TRACKING_LOG.md`](file:///f:/supremeai/audit_reports/supreme-deep-audit-reports/FEATURE_TRACKING_LOG.md) | **Feature Tracking Log** | System documentation and operational guidance file. |
| 50 | [`audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md`](file:///f:/supremeai/audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md) | **MANUAL_STEPS.md** | System documentation and operational guidance file. |

## backend

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 51 | [`backend/COVERAGE_90_PLAN.md`](file:///f:/supremeai/backend/COVERAGE_90_PLAN.md) | **Coverage 100% Plan** | System documentation and operational guidance file. |
| 52 | [`backend/README.md`](file:///f:/supremeai/backend/README.md) | **SupremeAI Backend** | The worker exposes separate operational signals: `/health/live` confirms only that the process is running, `/health/ready` confirms that the configured queue... |
| 53 | [`backend/TEST_COVERAGE_PLAN.md`](file:///f:/supremeai/backend/TEST_COVERAGE_PLAN.md) | **SupremeAI 2.0 — 100% Test Coverage Implementation Plan** | 1. **core/cache/redis_manager.py** - SecureRedisManager, IdempotencyLock |
| 54 | [`backend/_INDEX.md`](file:///f:/supremeai/backend/_INDEX.md) | **backend/ — File Index** | System documentation and operational guidance file. |
| 55 | [`backend/core/RETRY_HANDLER_DOCS.md`](file:///f:/supremeai/backend/core/RETRY_HANDLER_DOCS.md) | **রিট্রাই হ্যান্ডলার ডকুমেন্টেশন (Retry Handler Documentation)** | রিট্রাই হ্যান্ডলার হল একটি পাওয়ারফুল ডেকোরেটর যা অস্থায়ী ব্যর্থতা থেকে সুষ্ঠুভাবে রিকভার করতে সাহায্য করে। এটি এক্সপোনেনশিয়াল ব্যাকঅফ, জিটার, এবং রিট্রাই ... |
| 56 | [`backend/core/_INDEX.md`](file:///f:/supremeai/backend/core/_INDEX.md) | **backend/core/ — File Index** | System documentation and operational guidance file. |
| 57 | [`backend/core/cache/README.md`](file:///f:/supremeai/backend/core/cache/README.md) | **Cache Management** | This directory provides the core caching infrastructure for the SupremeAI project, designed to significantly optimize performance, reduce operational costs, ... |
| 58 | [`backend/database/migrations/README.md`](file:///f:/supremeai/backend/database/migrations/README.md) | **Database Migration Directory** | The **only active migration system** for SupremeAI is **Alembic**, located at `backend/alembic_migrations/`. All new schema changes must be made as Alembic m... |
| 59 | [`backend/docker/Current Agents & future plan in the Project.md`](file:///f:/supremeai/backend/docker/Current Agents & future plan in the Project.md) | **Current Agents & future plan in the Project.md** | Current Agents in the Project |
| 60 | [`backend/docs/autogen/LATEST-PUSH-SUMMARY.md`](file:///f:/supremeai/backend/docs/autogen/LATEST-PUSH-SUMMARY.md) | **SupremeAI Push Summary (22eff1f7cf)** | Failed to generate summary via LLM: litellm.AuthenticationError: GeminiException - { |
| 61 | [`backend/docs/autogen/changes/changelog_full.md`](file:///f:/supremeai/backend/docs/autogen/changes/changelog_full.md) | **📜 SupremeAI 2.0 Centralized Changelog** | commit 5b044ac9872854baf20b797b903716b550685e82 |
| 62 | [`backend/docs/autogen/summaries/PUSH-SUMMARY-22eff1f7cf.md`](file:///f:/supremeai/backend/docs/autogen/summaries/PUSH-SUMMARY-22eff1f7cf.md) | **SupremeAI Push Summary (22eff1f7cf)** | Failed to generate summary via LLM: litellm.AuthenticationError: GeminiException - { |
| 63 | [`backend/issues_summary.md`](file:///f:/supremeai/backend/issues_summary.md) | **SupremeAI 2.0 এর Render লগ থেকে পাওয়া সমস্যাগুলির সারাংশ** | ERROR: Primary DB (Supabase) failed: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain (_ssl.c:1016). |
| 64 | [`backend/reports/chaos_report.md`](file:///f:/supremeai/backend/reports/chaos_report.md) | **🧪 SupremeAI Chaos Engineering Report** | System documentation and operational guidance file. |
| 65 | [`backend/tools/knowledge/README.md`](file:///f:/supremeai/backend/tools/knowledge/README.md) | **backend/tools/knowledge** | This directory houses a comprehensive suite of modules dedicated to the extraction, indexing, and management of diverse forms of knowledge for the SupremeAI ... |

## docs (Root)

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 66 | [`docs/DOCUMENTATION_MASTER_INDEX.md`](file:///f:/supremeai/docs/DOCUMENTATION_MASTER_INDEX.md) | **SupremeAI — Master Documentation Inventory & Index** | This document provides a comprehensive, centralized index of all documentation, specification, and operational markdown (`.md`) files in the SupremeAI reposi... |

## docs/master_docs

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 67 | [`docs/master_docs/AIBRAIN-01-MASTER_AGENT_SPECIFICATION.md`](file:///f:/supremeai/docs/master_docs/AIBRAIN-01-MASTER_AGENT_SPECIFICATION.md) | **09 — AI Brain & Agents** | <!-- ============================================================ --> |
| 68 | [`docs/master_docs/ARCH-01-MASTER_CONSTITUTION.md`](file:///f:/supremeai/docs/master_docs/ARCH-01-MASTER_CONSTITUTION.md) | **01 — Overview** | <!-- ============================================================ --> |
| 69 | [`docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md`](file:///f:/supremeai/docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md) | **02 — Architecture** | str = Field(..., description="ক্যাপাবিলিটির বিবরণ") |
| 70 | [`docs/master_docs/ARCH-03-DATA_AND_STORAGE_PLAN.md`](file:///f:/supremeai/docs/master_docs/ARCH-03-DATA_AND_STORAGE_PLAN.md) | **08 — Database** | <!-- ============================================================ --> |
| 71 | [`docs/master_docs/ARCH-05-MASTER_ROADMAP_AND_DECISIONS.md`](file:///f:/supremeai/docs/master_docs/ARCH-05-MASTER_ROADMAP_AND_DECISIONS.md) | **SupremeAI - Technical Specification Document** | <!-- ============================================================ --> |
| 72 | [`docs/master_docs/BACKEND-01-API_REFERENCE_AND_CONTRACTS.md`](file:///f:/supremeai/docs/master_docs/BACKEND-01-API_REFERENCE_AND_CONTRACTS.md) | **05 — Backend** | <!-- ============================================================ --> |
| 73 | [`docs/master_docs/BACKEND-07-MICROSERVICES_AND_PLUGINS.md`](file:///f:/supremeai/docs/master_docs/BACKEND-07-MICROSERVICES_AND_PLUGINS.md) | **10 — Monorepo Packages** | <!-- ============================================================ --> |
| 74 | [`docs/master_docs/DEVOPS-01-PURE_CLOUD_INFRASTRUCTURE.md`](file:///f:/supremeai/docs/master_docs/DEVOPS-01-PURE_CLOUD_INFRASTRUCTURE.md) | **13 — Deployment** | <!-- ============================================================ --> |
| 75 | [`docs/master_docs/FRONTEND-01-DESIGN_SYSTEM_AND_TOKENS.md`](file:///f:/supremeai/docs/master_docs/FRONTEND-01-DESIGN_SYSTEM_AND_TOKENS.md) | **06 — Frontend** | <!-- ============================================================ --> |
| 76 | [`docs/master_docs/INTEG-01-MCP_INTEGRATION_HANDBOOK.md`](file:///f:/supremeai/docs/master_docs/INTEG-01-MCP_INTEGRATION_HANDBOOK.md) | **💻 SupremeAI Clients & Thin-Runtime Master Plan** | <!-- ============================================================ --> |
| 77 | [`docs/master_docs/INTEG-06-VSCODE_EXTENSION_AND_IDE.md`](file:///f:/supremeai/docs/master_docs/INTEG-06-VSCODE_EXTENSION_AND_IDE.md) | **11 — VS Code Extension** | <!-- ============================================================ --> |
| 78 | [`docs/master_docs/OPS-01-TESTING_STRATEGY_AND_TIERS.md`](file:///f:/supremeai/docs/master_docs/OPS-01-TESTING_STRATEGY_AND_TIERS.md) | **12 — Testing** | <!-- ============================================================ --> |
| 79 | [`docs/master_docs/OPS-04-OPERATIONAL_RUNBOOKS_AND_TASKS.md`](file:///f:/supremeai/docs/master_docs/OPS-04-OPERATIONAL_RUNBOOKS_AND_TASKS.md) | **15 — Operations** | <!-- ============================================================ --> |
| 80 | [`docs/master_docs/SEC-01-30_CATEGORY_SECURITY_MATRIX.md`](file:///f:/supremeai/docs/master_docs/SEC-01-30_CATEGORY_SECURITY_MATRIX.md) | **14 — Security** | Staging base URL (default: env STAGING_BASE_URL) |

## frontend

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 81 | [`frontend/README.md`](file:///f:/supremeai/frontend/README.md) | **React + TypeScript + Vite** | This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules. |
| 82 | [`frontend/_INDEX.md`](file:///f:/supremeai/frontend/_INDEX.md) | **frontend/ — File Index** | System documentation and operational guidance file. |
| 83 | [`frontend/src/FRONTEND_SIMPLICITY.md`](file:///f:/supremeai/frontend/src/FRONTEND_SIMPLICITY.md) | **Frontend simplicity contract** | The frontend is a viewer and interaction layer, not a second backend. |
| 84 | [`frontend/src/commandcenter/TODO.md`](file:///f:/supremeai/frontend/src/commandcenter/TODO.md) | **AETHEL Command Center — Implementation TODO** | System documentation and operational guidance file. |
| 85 | [`frontend/src/store/_legacy_stores.md`](file:///f:/supremeai/frontend/src/store/_legacy_stores.md) | **R13 — Legacy Zustand Stores Migration Map** | These 12 stores are targeted for consolidation into `unifiedStore.ts`. |

## infrastructure

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 86 | [`infrastructure/mcp-control-plane/PROVIDER_NEUTRAL_CONNECTIONS.md`](file:///f:/supremeai/infrastructure/mcp-control-plane/PROVIDER_NEUTRAL_CONNECTIONS.md) | **Provider-neutral MCP connections** | SupremeAI exposes one provider-neutral MCP endpoint. Customers may connect any MCP-compatible AI client; the server does not assume Claude, Cursor, or a spec... |

## reports

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 87 | [`reports/codebase_fixes_applied.md`](file:///f:/supremeai/reports/codebase_fixes_applied.md) | **SupremeAI 2.0 — Fixes Applied** | 1. ✅ **Removed RBAC bypass flag** — `backend/core/security/rbac.py:172-174` |
| 88 | [`reports/codebase_issues_report.md`](file:///f:/supremeai/reports/codebase_issues_report.md) | **SupremeAI 2.0 — Verified Codebase Issues Report** | After verifying actual code state, **many previously reported issues are already FIXED**. This report only includes **verified open issues**. |

## scripts

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 89 | [`scripts/_INDEX.md`](file:///f:/supremeai/scripts/_INDEX.md) | **scripts/ — Script Index (AUTO-GENERATED)** | Hand-curated sections live inside `<!-- hand:Name -->` … `<!-- /hand:Name -->` blocks |
| 90 | [`scripts/ci/README-config-registry-migration.md`](file:///f:/supremeai/scripts/ci/README-config-registry-migration.md) | **Registry evidence workflow** | Run from the repository root: |
| 91 | [`scripts/docs/BROWSER_CROWN_JEWEL_INTEGRATION_GUIDE.md`](file:///f:/supremeai/scripts/docs/BROWSER_CROWN_JEWEL_INTEGRATION_GUIDE.md) | **🌐 Crown Jewel Browser - Integration Patch (diff.patch format)** | +++ b/frontend/src/components/admin/CommandCenter.tsx |
| 92 | [`scripts/docs/CONSOLE_DETECTIVE_README.md`](file:///f:/supremeai/scripts/docs/CONSOLE_DETECTIVE_README.md) | **🔍 SuperAI Browser Console Detective** | 1. Error দেখতে চান এমন Website Open করুন |

## specs

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 93 | [`specs/001-dynamic-production-configuration/checklists/configuration.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/checklists/configuration.md) | **Configuration Governance Requirements Checklist: 001-dynamic-production-configuration** | System documentation and operational guidance file. |
| 94 | [`specs/001-dynamic-production-configuration/contracts/config-contract.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/contracts/config-contract.md) | **Interface Contract — Canonical Configuration Keys** | Feature: 001-dynamic-production-configuration · Date: 2026-08-29 |
| 95 | [`specs/001-dynamic-production-configuration/data-model.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/data-model.md) | **Phase 1 — Data Model (configuration domain)** | Feature: 001-dynamic-production-configuration · Date: 2026-08-29 |
| 96 | [`specs/001-dynamic-production-configuration/plan.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/plan.md) | **Implementation Plan: Production Configuration & Dynamic Endpoint Hardening** | Make SupremeAI's production configuration deployment-agnostic by establishing one |
| 97 | [`specs/001-dynamic-production-configuration/quickstart.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/quickstart.md) | **Quickstart — Validation Drills** | Feature: 001-dynamic-production-configuration · Date: 2026-08-29 |
| 98 | [`specs/001-dynamic-production-configuration/research.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/research.md) | **Phase 0 — Research & Decisions** | Feature: 001-dynamic-production-configuration · Date: 2026-08-29 |
| 99 | [`specs/001-dynamic-production-configuration/spec.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/spec.md) | **Feature Specification: Production Configuration & Dynamic Endpoint Hardening** | Make SupremeAI production configuration deployment-agnostic. Users and admins must be able to use the correct backend without hardcoded deployment URLs in ap... |
| 100 | [`specs/001-dynamic-production-configuration/tasks.md`](file:///f:/supremeai/specs/001-dynamic-production-configuration/tasks.md) | **Tasks: 001-dynamic-production-configuration** | System documentation and operational guidance file. |
| 101 | [`specs/002-policy-driven-web-crawler/contracts/python-interface.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/contracts/python-interface.md) | **Python Interface Contracts: `backend/scout/`** | class CrawlRequest(BaseModel): |
| 102 | [`specs/002-policy-driven-web-crawler/data-model.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/data-model.md) | **Data Model: Policy-Driven Web Crawler Upgrade** | Defines the boundary, limits, and pacing rules for all crawling within a tenant workspace. |
| 103 | [`specs/002-policy-driven-web-crawler/plan.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/plan.md) | **Implementation Plan: Policy-Driven Web Crawler Upgrade** | Upgrade `backend/scout/` from a minimal 14-line stub and single-page fetcher into a robust, policy-driven web crawler: |
| 104 | [`specs/002-policy-driven-web-crawler/quickstart.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/quickstart.md) | **Quickstart Validation Guide: Policy-Driven Web Crawler** | Run the dedicated test suite for the crawler components: |
| 105 | [`specs/002-policy-driven-web-crawler/research.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/research.md) | **Research & Architecture Decisions: Policy-Driven Web Crawler Upgrade** | Store `CrawlPolicy`, `DomainRule`, and `CrawlHistory` using PostgreSQL (via the existing SQLAlchemy 2.0 async session and tenant models in `backend/database/... |
| 106 | [`specs/002-policy-driven-web-crawler/spec.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/spec.md) | **Feature Specification: Policy-Driven Web Crawler Upgrade** | Upgrade the existing web-crawling capability (currently a minimal stub plus a single-page fetcher) into a policy-driven crawler: operator-configurable crawl ... |
| 107 | [`specs/002-policy-driven-web-crawler/tasks.md`](file:///f:/supremeai/specs/002-policy-driven-web-crawler/tasks.md) | **Tasks: Policy-Driven Web Crawler Upgrade** | System documentation and operational guidance file. |

## tools

| # | File Path / Name | Title / Header | Purpose & Summary |
| :--- | :--- | :--- | :--- |
| 108 | [`tools/autonomy/README.md`](file:///f:/supremeai/tools/autonomy/README.md) | **SupremeAI Autonomy Pack** | Reusable, dependency-light scripts designed to turn SupremeAI into a self-improving engineering platform. |
| 109 | [`tools/discovery_fabric/README.md`](file:///f:/supremeai/tools/discovery_fabric/README.md) | **SupremeAI Discovery Fabric** | A reusable discovery layer for SupremeAI to answer four questions before it implements a solution: |
| 110 | [`tools/gap_miner/README.md`](file:///f:/supremeai/tools/gap_miner/README.md) | **SupremeAI Gap Miner** | A reusable, read-only project intelligence toolkit for SupremeAI and other software projects. |
| 111 | [`tools/intelligence_extensions/README.md`](file:///f:/supremeai/tools/intelligence_extensions/README.md) | **SupremeAI Intelligence Extension Pack v1** | Ten production-oriented extension modules: |
| 112 | [`tools/knowledge_squeezer/README.md`](file:///f:/supremeai/tools/knowledge_squeezer/README.md) | **SupremeAI Knowledge Squeezer** | A production-oriented foundation for turning multi-model brainstorming into reusable |
| 113 | [`tools/knowledge_squeezer/SUGGESTED_NEW_SCRIPTS.md`](file:///f:/supremeai/tools/knowledge_squeezer/SUGGESTED_NEW_SCRIPTS.md) | **Scripts that would make SupremeAI materially stronger** | Turns each important claim into verifiable subclaims and asks independent tools/sources |
| 114 | [`tools/solution_synthesizer/README.md`](file:///f:/supremeai/tools/solution_synthesizer/README.md) | **SupremeAI Solution Synthesizer — The Hand** | It accepts a diagnostic issue, gathers targeted code context, asks a configurable AI solver for a **minimal structured patch**, validates the patch, applies ... |
| 115 | [`tools/vscode-extension/ARCHITECTURE_BN.md`](file:///f:/supremeai/tools/vscode-extension/ARCHITECTURE_BN.md) | **সুপ্রিমএআই VS Code এক্সটেনশন - আর্কিটেকচার গাইড (বাংলায়)** | সুপ্রিমএআই একটি **রিয়েল-টাইম মেশিন লার্নিং-ভিত্তিক এআই-ড্রাইভেন ডেভেলপমেন্ট সহায়ক**। এটি VS Code এক্সটেনশন হিসেবে কাজ করে এবং ব্যবহারকারীর কোডিং প্যাটার্নকে... |
| 116 | [`tools/vscode-extension/CHANGELOG.md`](file:///f:/supremeai/tools/vscode-extension/CHANGELOG.md) | **Changelog — SupremeAI VS Code Extension** | All notable changes to the SupremeAI Extension will be documented in this file. |
| 117 | [`tools/vscode-extension/INTEGRATION_GUIDE_BN.md`](file:///f:/supremeai/tools/vscode-extension/INTEGRATION_GUIDE_BN.md) | **SupremeAI VS Code Extension - Full Integration Guide (বাংলায়)** | VS Code Extension (এই এক্সটেনশন) |
| 118 | [`tools/vscode-extension/README.md`](file:///f:/supremeai/tools/vscode-extension/README.md) | **SupremeAI VS Code Extension** | Real-time code learning and AI assistance directly in your IDE. Every code edit, error, and feedback you provide trains the SupremeAI core engine instantly. |
| 119 | [`tools/vscode-extension/README_BANGLA.md`](file:///f:/supremeai/tools/vscode-extension/README_BANGLA.md) | **সুপ্রিমএআই ভিএসকোড এক্সটেনশন** | সুপ্রিমএআই ভিএসকোড এক্সটেনশন হল একটি এআই-পাওয়ার্ড ডেভেলপমেন্ট সহায়ক যা ডেভেলপারদের কোড লেখা, বোঝা, এবং উন্নত করতে সাহায্য করে। এটি eLai কোড এক্সটেনশনের সের... |
| 120 | [`tools/vscode-extension/_INDEX.md`](file:///f:/supremeai/tools/vscode-extension/_INDEX.md) | **tools/vscode-extension/ — File Index** | User → Extension (Thin Client) → SupremeAI Backend → [LLM providers hidden] |

