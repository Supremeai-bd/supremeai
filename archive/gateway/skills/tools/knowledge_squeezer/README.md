# SupremeAI Knowledge Squeezer

A production-oriented foundation for turning multi-model brainstorming into reusable
knowledge artifacts.

## Pipeline

1. Independent generation
2. Cross-model adversarial audit
3. Socratic gap mining
4. First-principles reconstruction
5. Structured synthesis
6. Confidence/scoring gate
7. Optional promotion to SupremeAI long-term memory

## Environment

At least one provider key is required:

- `DEEPSEEK_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

Optional model overrides:

- `DEEPSEEK_MODEL`
- `ANTHROPIC_MODEL`
- `GEMINI_MODEL`
- `DEEPSEEK_BASE_URL`

Install provider SDKs as needed:

```bash
pip install openai anthropic google-genai
```

Run:

```bash
python scripts/knowledge_squeezer.py "How should a distributed cache invalidate safely?"
```

## Integration

The `memory_adapter.py` builds the payload expected by the existing SupremeAI
long-term memory interface. Wire `write_via_unified_memory()` to your actual
memory service object rather than inserting into the database directly.

## Production hardening still needed

- real semantic contradiction detection
- retrieval-based evidence verification
- executable tests for code claims
- provenance/version tracking
- knowledge expiry/revalidation
- tenant-aware memory ACLs
- cost-aware model routing
- circuit breakers and rate limits
