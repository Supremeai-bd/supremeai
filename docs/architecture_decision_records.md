# SupremeAI 2026: Architecture Decision Records (ADRs)

## 1. Multi-Agent Swarm (LivingEngine)
**Date:** August 2026
**Status:** Adopted
**Context:** The system needs to dynamically route between specialized LLMs to optimize cost and performance.
**Decision:** We adopt a Swarm architecture with a Central Orchestrator (`LivingEngineOrchestrator`) that evaluates intents, branches into a Tree of Thought, and delegates to specialized agents (DevOps, Security, etc.) using `LLMGateway`.
**Consequences:** Increased flexibility but requires rigorous rate limiting and fallback chains to ensure stability.

## 2. Global Logging Standardization
**Date:** August 2026
**Status:** Adopted
**Context:** Python's standard `logging` lacks color support out-of-the-box and requires significant boilerplate for async thread-safe execution.
**Decision:** We adopt `loguru` globally in the backend. 
**Consequences:** Removes all `import logging`, improves developer experience and JSON structured logging.

## 3. Zustand Store Consolidation
**Date:** August 2026
**Status:** Adopted
**Context:** Frontend has 13+ fragmented stores, causing circular imports and prop-drilling complexity.
**Decision:** We consolidate state management into 5 core slices: `authSlice`, `chatSlice`, `agentSlice`, `adminSlice`, `uiSlice` using the slice pattern in `unifiedStore`.
**Consequences:** Simplifies state management, but requires careful migration to avoid breaking existing React components.

## 4. Asynchronous Database Layer
**Date:** August 2026
**Status:** Adopted
**Context:** Synchronous `psycopg2` blocks FastAPI's event loop during heavy concurrent traffic.
**Decision:** We migrate to `asyncpg` globally with SQLAlchemy 2.0.
**Consequences:** Vastly improved throughput, but debugging async DB sessions requires careful attention to lazy loading exceptions.
