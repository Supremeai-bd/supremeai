# SupremeAI Documentation

> **একটা সিস্টেমের প্রতিটি মডিউল, কম্পোনেন্ট — একটা আরেকটার প্রতিযোগী না।**
> **সব মিলে একটা ফুল সিস্টেম হয়।** ডকুমেন্টেশনও তেমন — একটা জীবন্ত গ্রাফ,
> ফাইলের সংগ্রহ না। প্রতিটা প্ল্যান এই ইকোসিস্টেমের অংশ।

```
১৮৩টা প্ল্যান ফাইল  →  ১২টা canonical শাখা  →  ১টা relationship লেয়ার
```

---

## Start here

| If you want to... | Read this |
|--------------------|-----------|
| **ইকোসিস্টেম দর্শন বুঝতে (প্রথমে এটি)** | **[ECOSYSTEM_PHILOSOPHY.md](./ECOSYSTEM_PHILOSOPHY.md)** |
| understand *why* SupremeAI exists | [vision/principles.md](./vision/principles.md) |
| see what SupremeAI is made of | [architecture/system.md](./architecture/system.md) + [architecture/domains.md](./architecture/domains.md) |
| see every plan and its relationships | [plans/PLAN_REGISTRY.md](./plans/PLAN_REGISTRY.md) |
| see the dependency graph | [plans/PLAN_GRAPH.md](./plans/PLAN_GRAPH.md) |
| see who depends on whom | [plans/PLAN_MATRIX.md](./plans/PLAN_MATRIX.md) |
| know if a plan is real | [plans/PLAN_STATUS_LIFECYCLE.md](./plans/PLAN_STATUS_LIFECYCLE.md) |
| add a new plan | [plans/IMPACT_MAP.md](./plans/IMPACT_MAP.md) + [plans/_templates/PLAN_TEMPLATE.md](./plans/_templates/PLAN_TEMPLATE.md) |
| migrate the legacy jungle | [plans/MIGRATION_MAP.md](./plans/MIGRATION_MAP.md) |
| see what's being built | [execution/github-mapping.md](./execution/github-mapping.md) |
| see how we verify | [verification/audits.md](./verification/audits.md) + [verification/production-checks.md](./verification/production-checks.md) |

---

## The 5 layers

```text
Layer 1 · Direction       →  vision/principles.md
Layer 2 · Architecture    →  architecture/system.md + domains.md
Layer 3 · Strategic Plans →  plans/PLAN_REGISTRY.md (+ graph + matrix)
Layer 4 · Execution       →  execution/github-mapping.md
Layer 5 · Verification    →  verification/audits.md + production-checks.md
```

---

## Directory layout

```text
docs/
├── README.md                      ← you are here
├── vision/
│   └── principles.md              ← Layer 1: vision + 7 principles + non-negotiables
├── architecture/
│   ├── system.md                  ← Layer 2: the 5-layer model + system map
│   └── domains.md                 ← Layer 2: the 9 domains
├── plans/
│   ├── PLAN_REGISTRY.md           ← Layer 3: the index (12 plans, one row each)
│   ├── PLAN_GRAPH.md              ← Layer 3: mermaid dependency graph
│   ├── PLAN_MATRIX.md             ← Layer 3: dependency + reverse-dependency matrix
│   ├── PLAN_STATUS_LIFECYCLE.md   ← Layer 3: status state machine
│   ├── IMPACT_MAP.md              ← Layer 3: new-plan intake checklist
│   ├── MIGRATION_MAP.md           ← Layer 3: 188 files → 12 plans
│   ├── _templates/
│   │   └── PLAN_TEMPLATE.md       ← canonical plan template (with relationship header)
│   ├── security/                  ← P01
│   ├── intelligence/              ← P02, P05
│   ├── mcp/                       ← P03
│   ├── agents/                    ← P04
│   ├── automation/                ← P06
│   ├── experience/                ← P07
│   ├── infrastructure/            ← P08
│   ├── observability/             ← P09
│   └── governance/                ← P10, P11, P12
├── execution/
│   └── github-mapping.md          ← Layer 4: plan → milestone → issue
└── verification/
    ├── audits.md                  ← Layer 5: audit surfaces
    └── production-checks.md       ← Layer 5: SLOs + runtime hooks
```

---

## The one rule

> **One concept → one canonical document → many references.**
>
> If you find two documents covering the same topic, one of them is wrong.
> Merge them. The [Plan Registry](./plans/PLAN_REGISTRY.md) is the only index.
