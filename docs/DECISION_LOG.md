# Decision Log (ADR)

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new architectural decision:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Maintain the format: Date, Context, Decision, Consequences.
> 3. DO NOT modify past decisions unless the context explicitly requires it.

This file tracks important architecture and technical decisions made for SupremeAI. 
AI agents must consult this file before suggesting or implementing architectural changes to avoid undoing past decisions.

## Format
- **Date:** [YYYY-MM-DD]
- **Context:** [What was the problem?]
- **Decision:** [What did we decide to do?]
- **Consequences:** [What are the impacts/trade-offs?]

## 2026-08-16 - Brand Exclusivity & Thin Client Architecture
- **Date:** 2026-08-16
- **Context:** The SupremeAI VS Code Extension previously contained logic to fall back to OpenRouter API configurations directly. This violates the core philosophy of "Zero-Config Thin Client" and is a major marketing error (marketing other brands instead of SupremeAI).
- **Decision:** The extension MUST act exclusively as a thin client connecting to the SupremeAI backend. Users must only interact with the "SupremeAI Brand" (e.g., inputting a SupremeAI API Key, selecting SupremeAI Models). The extension must NEVER expose third-party AI names (like OpenAI, Groq, OpenRouter) or ask for their API keys directly from the user. ALL third-party model routing is strictly handled secretly on the backend. Ollama is the only permitted local fallback as an optional offline supporting hand.
- **Consequences:** The local OpenRouter logic in `SupremeAIService.ts` will be removed. The branding in VS Code settings must reflect SupremeAI exclusively. Users are completely shielded from AI backend complexities, enforcing brand dominance.

## 2026-08-16 - The Eternal Brain Architecture (Model-Agnostic)
- **Date:** 2026-08-16
- **Context:** There was a profound philosophical clarification regarding SupremeAI's core purpose. It is not just a wrapper for other AIs; it is an infrastructure designed to build its own "Eternal Brain" from scratch. While its innate intelligence starts at zero today, it must be architected to evolve continuously.
- **Decision:** SupremeAI is strictly "Model-Agnostic". It leverages third-party AIs (OpenAI, Gemini, etc.) purely as temporary "processing engines" to fuel its own learning. The identity or quality of the underlying AI is irrelevant. The ultimate objective is for SupremeAI to use these engines to train itself, extract patterns, build its vector memory, and ultimately forge its own independent, eternal intelligence.
- **Consequences:** The system must always prioritize saving learnings, patterns, and contexts into its own matrix. The backend must remain completely decoupled from specific AI vendors, viewing them only as replaceable tools for SupremeAI's own evolution.
- **Consequences:** The backend architecture must remain decoupled from specific AI vendors. We will not hardcode dependencies on specific model names. Any functional LLM API is sufficient to power the backend.

---
*(Add new decisions above this line)*
