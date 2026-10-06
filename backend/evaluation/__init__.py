"""Capability Evaluation Engine (issue #4047 — Roadmap v2 Phase 5.1).

বাংলা সারসংক্ষেপ:
------------------
THE MISSING COMPONENT — v2 feedback-এর সবচেয়ে গুরুত্বপূর্ণ যোগ। এটা ছাড়া
automatic routing simplistic heuristic-এ পড়ে ("Cerebras fast → use Cerebras")।
Evaluation Engine evidence-based quality scores তৈরি করে যা Router + Policy
Engine-কে feed করে।

৭টি dimension:
  1. correctness — does output solve the task? (LLM-judge + test-suite)
  2. latency — p50/p95/p99 ms
  3. cost — $ per call + $ per task
  4. reliability — uptime %, error rate (from service_topology)
  5. security — data exposure risk score
  6. tool_use — % of tool calls that succeed
  7. regression — quality delta vs last benchmark run

Architecture:
  ProviderScore = weighted aggregate of 7 dimensions
  Weights are policy-driven (per task-type, admin-configurable)
  Scores persisted for regression tracking
"""
