# 🔱 SupremeAI 2.0

SupremeAI 2.0 is an ambitious, production-grade multi-cloud AI orchestration platform built for developers and organizations who need resilient, cost-efficient, and secure LLM routing. It solves the problem of high API costs, single-provider dependency, and model hallucinations by orchestrating across 8+ free-tier AI providers with a built-in 6-layer defense mechanism.

---

## 🌟 Key Highlights

*   **Zero-Cost Orchestration:** Intelligently leverages free-tiers across 8+ AI providers (OpenAI, Google Gemini, Anthropic, Groq, Cohere, etc.) with automatic fallback routing.
*   **6-Layer Hallucination Defense:** Advanced guardrails checking schema conformance, prompt injection protection, secret masking, and verification of LLM responses.
*   **Self-Evolution Engine:** A dynamic skill registry allowing the system to monitor repeated failures, propose optimized prompt templates, and draft new capabilities.
*   **Multi-Cloud Redundancy:** Actively deployed across GCP Cloud Run, Firebase Hosting, Render, Railway, and Cloudflare Workers load balancers for under $5/month.

---

## 📁 Repository Structure

```text
supremeai/
├── backend/                  # FastAPI backend (Python 3.11+, Poetry)
├── apps/
│   ├── studio-client/        # React + Vite admin/developer studio UI
│   ├── mobile/               # Flutter mobile application
│   └── web-chat/             # React web client interface
├── tools/
│   └── vscode-extension/     # TypeScript VS Code extension
├── docs/                     # Comprehensive numbered documentation (00-10)
├── evolution/                # Self-learning and skill proposal engine
├── infrastructure/           # Terraform, Cloudflare Workers, & Firebase config
└── scripts/                  # Bootstrapping, deployment, and runner scripts
```

---

## 🚀 Getting Started

Quickly spin up the environment using our helper scripts:

```bash
# Bootstrap the development environment (venv, dependencies)
python scripts/bootstrap_env.py

# Setup local runners
bash scripts/runner/setup_runner.sh local

# Start the FastAPI backend
pnpm backend:dev
```

For a comprehensive guide, refer to the [Local Setup Guide](file:///c:/Users/n/supremeai/supremeai_2.0/LOCAL_SETUP_GUIDE.md).

---

## 📚 Documentation Index

Our documentation is strictly organized by functional area to maintain engineering discipline:

1.  **[docs/01-project/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/01-project)**: Product vision, tech comparisons, and OKRs.
2.  **[docs/02-governance/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/02-governance)**: AI behaviors, rules, and guidelines.
3.  **[docs/03-architecture/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/03-architecture)**: System architecture design blueprints and ADR logs.
4.  **[docs/04-development/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/04-development)**: Onboarding guides and implementation plans.
5.  **[docs/05-operations/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/05-operations)**: Deployments, monitors, and Cloud runbooks.
6.  **[docs/06-api/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/06-api)**: Endpoint specifications and OpenAPI contracts.
7.  **[docs/07-testing/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/07-testing)**: Testing strategies and coverage guidelines.
8.  **[docs/08-roadmap/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/08-roadmap)**: `PROJECT_STATUS` tracking and release logs.
9.  **[docs/09-security/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/09-security)**: Threat models, secrets management, and auditing.
10. **[docs/10-troubleshooting/](file:///c:/Users/n/supremeai/supremeai_2.0/docs/10-troubleshooting)**: FAQs, common run errors, and resolutions.
