# ADR 0002: Self-Evolution Engine Security Boundaries & Gating

## Status
Proposed (Drafted: 2026-06-25)

## Context
The **Self-Evolution Engine** (`evolution/` and `backend/core/evolution_engine.py`) allows SupremeAI 2.0 to dynamically adapt by learning from task successes and failures. However, unchecked autonomous self-modification (e.g., writing new python files/skills and registering them automatically) presents severe operational and security risks:
1.  **Arbitrary Code Execution:** An LLM generating Python code and executing it could run malicious payloads, destroy data, or access protected environment credentials.
2.  **Logic Poisoning:** Flawed code proposed by LLMs could lead to compilation failures or infinite resource consumption loops, degrading platform availability.
3.  **Credential Leaks:** Rogue generated code might call unauthorized external APIs or transmit secret tokens.

## Decision
To mitigate these risks, we enforce strict security boundaries and human-approval gating for all code generation:

1.  **Draft-Only Isolation (Proposals Table):**
    *   The `EvolutionEngine` is strictly forbidden from directly writing code into active source paths (e.g. `backend/core/` or `skills/`).
    *   All generated code/skills must be stored as raw text in the `skill_proposals` table in the SQLite database with `status = 'proposed'`.

2.  **Human-in-the-Loop Gating:**
    *   No dynamically created skill can be imported or executed by the runtime orchestrator until an Admin specifically reviews the proposed code and updates its status to `approved` via the JWT-secured Admin endpoint.
    *   The transition from `proposed` to `registered` requires explicit admin action.

3.  **Execution Sandbox Boundaries (Planned):**
    *   Approved dynamic skills will be executed inside isolated, containerized, or restricted execution contexts with:
        *   No write access to the main codebase.
        *   Limited network egress (only white-listed API endpoints).
        *   CPU and Memory quotas.

## Consequences
*   **Security:** Eliminates immediate risk of arbitrary code injection directly into the server runtime.
*   **Compliance & Auditability:** Every skill proposed by the AI engine leaves an immutable audit trail in the `skill_proposals` table, tracking when it was proposed and who/when approved it.
*   **Developer Friction:** Increases friction as new self-evolved skills require manual approval, but this is a necessary trade-off for production security.
