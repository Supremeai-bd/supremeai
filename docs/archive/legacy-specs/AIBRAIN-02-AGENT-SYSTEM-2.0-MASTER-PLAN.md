# AIBRAIN-02 — Agent System 2.0 Master Plan: Issue-Centric, Dual-Track, Queue-Zero Self-Auditing Agent Architecture

> **ডকুমেন্ট আইডি:** AIBRAIN-02 · **স্ট্যাটাস:** প্রস্তাবিত টার্গেট আর্কিটেকচার (PROPOSED) · **ভার্সন:** ১.০ (২০২৬-০৯-২৮)  
> **প্রযোজ্য:** সুপ্রিমএআই এজেন্ট ফ্লিট, টাস্ক অ্যাসাইনমেন্ট, কোঅর্ডিনেশন, অডিটিং, ভেরিফিকেশন, অটোমেশন  
> **মূল রেফারেন্স:** [`AIBRAIN-01`](AIBRAIN-01-MASTER_AGENT_SPECIFICATION.md) · [`ARCH-01`](ARCH-01-MASTER_CONSTITUTION.md) · [`ARCH-10`](ARCH-10-UNIVERSAL-ENGINE-MASTER-PLAN-GROUP-STAGING-RULE-ENGINE-BATCH-TRAIN-RED-TEAM.md) · [`AGENTS.md`](../../AGENTS.md)  
> **মূল নীতি:** Specialized Agents + Universal Issue Protocol + Lightweight Control Plane  
> **ভার্সন ১.০-এর বিস্তার:** PART I (§1–§37) = কোর আর্কিটেকচার · PART II (§38–§47) = Dual-Track Issues, Idle Plane (Queue-Zero Self-Audit) ও ১৭-ক্যাপাবিলিটি ফ্লিট অ্যাডেন্ডাম

> **Agents remain specialized. Work becomes issue-centric. Coordination becomes event/group-driven. Recurring work becomes time-driven. Agent-idle becomes audit-driven. Control Plane holds the "নাটাই"; Agent holds the implementation freedom.**

---

# PART I — CORE ARCHITECTURE (§1–§37)

## 1. The Core Change

SupremeAI-এর নতুন আর্কিটেকচারের উদ্দেশ্য **specialized agents বাদ দেওয়া নয়**।

বর্তমানে বিভিন্ন ধরনের Agent আছে এবং তাদের আলাদা capability আছে:

```text
Architecture
Coding
Review
Security
Testing
Browser
Documentation
...
```

এই specialization থাকবে।

কিন্তু Agent কীভাবে কাজ পাবে, কীভাবে অন্য কাজের সাথে coordinate করবে, কখন audit হবে, কখন verification হবে—এসবের জন্য আলাদা heavyweight Agent-to-Agent orchestration framework থাকবে না।

নতুন model:

```text
                    ISSUE
                      │
             Priority + AQL
                      │
                   Claim
                      │
                  Agent
                      │
                    Work
                      │
              Evidence / PR
                      │
          ┌───────────┴──────────┐
          ↓                      ↓
       CI/Event              Group State
          ↓                      ↓
      New Issue            Verification
```

### Fundamental principle

> **Agent provides capability.  
> Issue provides work.  
> Group provides context.  
> Event provides transition.  
> Time provides recurring work.  
> Control Plane provides boundaries.  
> CI provides fixed quality gates.**

## 2. Agent ≠ Workflow

এটাই আর্কিটেকচারের সবচেয়ে গুরুত্বপূর্ণ rule।

একটি Agent-এর role/capability থাকতে পারে, কিন্তু তার নিজের ভিতরে বিশাল workflow/orchestration system থাকবে না।

উদাহরণ:

```text
Coding Agent
```

মানে:

> এই Agent coding-related কাজ করতে পারে।

এর মানে এই নয়:

> Coding Agent-এর নিজস্ব handoff system, mailbox, swarm coordinator, reviewer chain ইত্যাদি থাকতে হবে।

একইভাবে:

```text
Auditor
Browser
Breaker
Security
Architecture
```

এগুলো capability/specialization।

**কাজের lifecycle Issue system পরিচালনা করবে।**

## 3. Universal Agent Work Protocol

সব Agent-এর common operating protocol:

```text
1. Issue খোঁজো
2. Group বুঝো
3. Priority দেখো
4. AQL / acceptance criteria পড়ো
5. Scope বুঝো
6. Existing architecture inspect করো
7. Issue claim করো
8. নির্ধারিত scope lock করো
9. কাজ করো
10. Evidence তৈরি করো
11. PR / Issue update করো
12. CI/verification-এর জন্য hand over করো
```

Agent-to-Agent direct handoff এখানে primary mechanism নয়।

### Primary coordination object:

**Issue / PR / CI / Group state**

## 4. Agent Capability Model

প্রতিটি Agent-এর দুটি layer থাকবে।

### A. Capability

Agent কী করতে পারে।

উদাহরণ:

```text
coding
architecture
security_analysis
testing
review
browser_execution
documentation
adversarial_testing
```

### B. Mission

বর্তমানে তাকে কী করতে বলা হয়েছে।

উদাহরণ:

```text
Fix Issue #421
Review PR #812
Audit Pipeline Group
Break authentication boundary
Check browser login flow
Verify third-party integration
```

তাই:

> **Capability স্থিতিশীল। Mission পরিবর্তনশীল।**

এটি Agent-কে অপ্রয়োজনীয় নতুন class/type দিয়ে ফুলিয়ে তুলতে বাধা দেবে।

## 5. Agent Fleet

বর্তমান specialized Agent ecosystem থাকবে।

উদাহরণ:

| Agent Capability | Primary responsibility |
| ---------------- | ---------------------- |
| Architecture     | architecture/design-related issues |
| Coding           | implementation/fix |
| Review           | PR/code verification |
| Security         | security-related analysis |
| Testing          | test/verification work |
| Browser          | browser-based execution |
| Documentation    | documentation/system knowledge |
| Auditor          | group/system audit |
| Breaker          | adversarial testing |
| Third-party      | external integration/provider verification |

এখানে নতুন capability প্রয়োজন হলে নতুন Agent class বানানো **default solution নয়**।

প্রথমে প্রশ্ন হবে:

> Existing Agent-এর capability + নতুন mission দিয়ে কাজটি করা যায় কি?

*(PART II §43-এ এই নিয়ম মেনেই ফ্লিট ১০ → ১৭ ক্যাপাবিলিটিতে সম্প্রসারিত হয়েছে।)*

## 6. Issue Is the Universal Work Unit

প্রতিটি কাজ Issue-তে প্রকাশিত হবে।

একটি Issue ideally ধারণ করবে:

```yaml
id:
group:
type:
priority:
scope:
aql:
dependencies:
constraints:
assigned_agent:
status:
evidence:
related_pr:
related_ci:
created_by:
created_at:
```

### Agent instruction নয়:

> "আজ Pipeline নিয়ে কাজ করো।"

### বরং:

> "Pipeline Group-এর Priority P1 Issue #421 claim করো এবং AQL satisfy করো।"

## 7. Priority

Priority Agent-এর নিজের সিদ্ধান্তের বিষয় নয়।

Issue-তে priority থাকবে।

উদাহরণ:

```text
P0 — Critical
P1 — High
P2 — Normal
P3 — Low
```

Queue/Control Plane priority অনুযায়ী কাজের order নির্ধারণ করবে।

Agent নিজের সুবিধামতো low-priority কাজ নিয়ে high-priority কাজ bypass করবে না।

## 8. AQL / Acceptance Criteria

প্রতিটি meaningful Issue-এর expected result machine-readable এবং human-readable উভয়ভাবে নির্ধারণ করা উচিত।

উদাহরণ:

```yaml
aql:
  must:
    - pipeline executes successfully
    - existing tests remain green
    - no production path broken

  verify:
    - CI passes
    - relevant tests pass
```

Agent implementation স্বাধীনভাবে করতে পারবে।

কিন্তু:

> **AQL পূরণ না হলে কাজ সম্পূর্ণ ধরা হবে না।**

এটাই Agent freedom এবং system control-এর balance।

## 9. Claim and Ownership

একটি Issue একসাথে বহু Agent claim করবে না।

```text
Issue
 ↓
Claim
 ↓
Agent
 ↓
Work Slot
 ↓
Branch
```

Claim mechanism lightweight script/control-plane দিয়ে পরিচালিত হবে।

উদাহরণ:

```text
acquire_work_slot.py
atomic_claim.sh
```

প্রয়োজনে Issue comment/metadata-তে:

```text
Agent: worker-03
Branch: coder-3
Touching files:
  - x.py
  - y.py
```

এতে parallel Agent conflict কমবে।

## 10. One Task → One Isolated Work Context

Default rule:

> **One Issue → one isolated branch/work context.**

একটি Group-এ ৪টি Issue থাকলে:

```text
Pipeline Group

Issue 1 → Branch A
Issue 2 → Branch B
Issue 3 → Branch C
Issue 4 → Branch D
```

এগুলো independently এগোতে পারবে।

Group-level verification পরে এগুলোকে একসাথে evaluate করবে।

## 11. Group Is Bigger Than an Issue

এটা নতুন আর্কিটেকচারের একটি key feature।

একটি বড় কাজকে Group হিসেবে define করা যাবে।

উদাহরণ:

```text
GROUP: PIPELINE REFACTOR

Issue #101
Pipeline architecture

Issue #102
CI workflow

Issue #103
Test coverage

Issue #104
Deployment integration
```

Group নিজে code change নয়।

Group হলো:

> **একটি logical objective-এর অধীনে থাকা related work-এর collection।**

## 12. Group Completion Event

যখন Group-এর required issues সম্পন্ন হয়:

```text
Issue 101 → complete
Issue 102 → complete
Issue 103 → complete
Issue 104 → complete
```

Control Plane detect করবে:

```text
GROUP_COMPLETED
```

তারপর automatically:

```text
Create Issue #105

Type:
GROUP_VERIFICATION

Group:
Pipeline Refactor
```

এখানে কোনো মানুষকে manually "এখন audit করো" বলতে হবে না।

## 13. Group Verification

Verification Issue-এর কাজ:

> পুরো Group-এর ফলাফল একসাথে পরীক্ষা করা।

উদাহরণ:

```text
Pipeline Group
     ↓
4 implementation issues complete
     ↓
Verification Issue
     ↓
Auditor/Reviewer claims
     ↓
Cross-issue verification
```

সে দেখবে:

* Group-এর সব requirement পূরণ হয়েছে?
* Issues একে অপরের সাথে conflict করছে?
* AQL পূরণ হয়েছে?
* CI green?
* Architecture consistency আছে?
* নতুন regression এসেছে?
* PR merge করার মতো অবস্থায় আছে?

## 14. Verification Outcomes

Verification Issue তিনটি প্রধান outcome দিতে পারবে:

### A. Allow

```text
GROUP VERIFIED
        ↓
Merge Train Eligible
```

### B. Reject

```text
GROUP VERIFICATION FAILED
        ↓
Existing work needs correction
        ↓
Reissue / remediation
```

### C. New Issue

```text
Audit discovered new problem
        ↓
Create new Issue
        ↓
Assign appropriate priority/group
```

অর্থাৎ Auditor-এর কাজ শুধু:

> "Pass/Fail"

না।

তার কাজ:

> **System-এর পরবর্তী required work-কে Issue system-এ ফিরিয়ে দেওয়া।**

## 15. Event-Driven Automation

Event-driven system-এর অর্থ:

> **কোনো meaningful system event ঘটলে automation নতুন state বা Issue তৈরি করবে।**

উদাহরণ:

```text
PR opened
PR updated
CI failed
CI passed
Issue completed
Group completed
Audit failed
Verification completed
Merge conflict
Deployment failed
```

প্রতিটি event-এর জন্য প্রয়োজন অনুযায়ী automation থাকতে পারে।

## 16. CI Failure → Automatic Issue

উদাহরণ:

```text
PR #500
   ↓
CI
   ↓
FAILED
```

Automation:

```text
CI_FAILURE event
       ↓
Find related PR/Issue
       ↓
Create or attach failure Issue
       ↓
Priority calculated
       ↓
Queue
       ↓
Suitable Agent
```

Agent manually CI dashboard scan করার ওপর system নির্ভর করবে না।

## 17. Event Chain

একটি event পরবর্তী Issue তৈরি করতে পারে।

উদাহরণ:

```text
CI failed
 ↓
Fix Issue
 ↓
Agent fixes
 ↓
CI passes
 ↓
Issue becomes ready
 ↓
Group completion
 ↓
Verification Issue
 ↓
Audit
 ↓
Pass
 ↓
Merge Train
```

এটা একটি **Issue/Event lifecycle**।

## 18. Time-Driven Automation

কিছু কাজ কোনো event-এর জন্য অপেক্ষা করবে না।

কারণ কিছু কাজ recurring।

তাই scheduler/script নির্দিষ্ট সময় পরপর Issue তৈরি করবে।

উদাহরণ:

```text
Every 6 hours
→ provider health issue

Every 12 hours
→ browser health issue

Every 24 hours
→ security audit issue

Every 7 days
→ architecture audit issue

Every 7 days
→ adversarial/breaker issue
```

কিন্তু গুরুত্বপূর্ণ rule:

> **Scheduler নিজে audit করে না। Scheduler Issue তৈরি করে।**

তারপর Agent Issue claim করে।

## 19. Auditor Model

Auditor সবসময় active থাকতে হবে না।

বরং:

```text
Time/Event
 ↓
Audit Issue
 ↓
Auditor-capable Agent
 ↓
Audit
 ↓
Evidence
 ↓
Findings
 ↓
New Issues
```

এতে idle resource কমবে এবং Agent fleet simpler থাকবে।

## 20. Breaker Model

Breaker-ও একই আর্কিটেকচার follow করবে।

Breaker-এর objective:

> **System-এর declared rules, assumptions, boundaries এবং protections ভাঙার চেষ্টা করা—authorized scope-এর মধ্যে।**

উদাহরণ:

```text
Time/Event
 ↓
Create Adversarial Audit Issue
 ↓
Breaker-capable Agent
 ↓
Read current rules
 ↓
Attempt authorized adversarial tests
 ↓
Collect evidence
 ↓
Issue if weakness found
```

Breaker নিজে permanent attack loop চালাবে না।

## 21. Breaker Is Not a Separate Orchestration System

এটা বিশেষভাবে document-এ পরিষ্কার রাখা উচিত।

```text
❌ BreakerAgent + BreakerCoordinator
❌ BreakerMailbox
❌ BreakerSwarm
❌ Breaker-specific handoff system
```

বরং:

```text
Breaker capability
       +
Adversarial Issue
       +
Existing Issue/Control Plane
```

## 22. Browser Agent

Browser capability-ও একই model:

```text
Browser Issue
 ↓
Browser-capable Agent
 ↓
Acquire session if needed
 ↓
Perform task
 ↓
Evidence
 ↓
Issue update
```

Idle browser session রাখার প্রয়োজন নেই।

Recurring browser health check:

```text
Scheduler
 ↓
Create Browser Health Issue
 ↓
Browser Agent
 ↓
Execute
 ↓
Report
```

## 23. Third-Party Agent

External providers/integrations-এর ক্ষেত্রেও একই pattern:

```text
Scheduled/Event
 ↓
Integration verification issue
 ↓
Third-party capable agent
 ↓
Test
 ↓
Evidence
 ↓
Pass / Failure Issue
```

Provider-specific orchestration system না বানিয়ে common Issue protocol ব্যবহার করা হবে।

## 24. Living Prompt

Agent-এর permanent prompt-এ বিশাল workflow hardcode করা হবে না।

`living_prompt.py` current state সংগ্রহ করবে:

```text
Current Issue
+
Group
+
Priority
+
AQL
+
Architecture
+
Relevant memory
+
Known failures
+
Constraints
+
Available capabilities
+
Current branch/workspace
+
Verification requirements
```

তারপর Agent-এর জন্য current mission তৈরি হবে।

```text
System State
      ↓
Living Prompt
      ↓
Specialized Agent
```

## 25. Agent Freedom vs Control Plane

এখানে **ঘুড়ি + নাটাই** principle থাকবে।

### Agent-এর হাতে

```text
Implementation strategy
Reasoning
Investigation method
Code approach
Test approach
Tool usage within permission
Problem solving
```

### Control Plane-এর হাতে

```text
Identity
Issue ownership
Priority
Scope
Branch
Permissions
Capabilities
Secrets
Tool access
Approval
Merge eligibility
Audit requirements
CI gates
```

### Principle

> **Agent decides how. Control Plane decides whether, where, and within what boundary.**

## 26. Fixed Gates Stay Fixed

সবকিছু Agent-এর intelligence-এর ওপর ছেড়ে দেওয়া যাবে না।

কিছু বিষয় deterministic থাকবে:

```text
CI
PR checks
branch protection
required tests
security gates
merge requirements
ownership/claim
permission boundaries
```

Agent বলতে পারবে না:

> "আমার reasoning অনুযায়ী CI দরকার নেই।"

CI হলো system gate।

## 27. PR Helper

PR helper lightweight এবং deterministic থাকবে।

তার কাজ হতে পারে:

```text
Issue ↔ PR relation
Group ↔ PR relation
AQL presence
required metadata
review state
merge readiness
```

এটি Agent-এর replacement নয়।

এটি Agent-এর কাজকে machine-verifiable করার infrastructure।

## 28. Merge Train

Merge Train হবে downstream controlled state।

```text
PR
 ↓
CI
 ↓
Review
 ↓
Group Verification
 ↓
Merge Eligibility
 ↓
Merge Train
```

Agent সরাসরি merge করার authority পাবে না যদি governance সেই permission না দেয়।

## 29. MCP Tower

MCP Tower থাকবে fleet/control infrastructure হিসেবে।

উদাহরণ:

```text
Agent
 ↓
Heartbeat
 ↓
Lease
 ↓
Capability / presence
 ↓
Control Plane
```

এটি:

* agent presence
* lease
* availability
* capability exposure
* runtime control

ইত্যাদি পরিচালনা করতে পারে।

কিন্তু business workflow-এর প্রতিটি step MCP Tower-এর ভিতরে ঢুকিয়ে heavyweight orchestrator বানানো উচিত নয়।

## 30. Memory

Agent কাজ শেষ করলে useful knowledge persistent memory-তে যেতে পারে।

কিন্তু memory হবে:

> **knowledge/evidence**

এবং Issue হবে:

> **work state**

এই দুটোকে এক করা যাবে না।

```text
Issue = What needs to be done / current work state

Memory = What the system learned
```

## 31. Failure Loop

Failure হলে system dead-end-এ যাবে না।

উদাহরণ:

```text
Agent work
 ↓
CI failed
 ↓
Failure Issue
 ↓
Agent fixes
 ↓
CI failed again
 ↓
same issue updated OR new issue
 ↓
escalation
```

একইভাবে:

```text
Audit
 ↓
Failure
 ↓
Remediation Issue
 ↓
Fix
 ↓
Re-Audit
```

## 32. Self-Improving Issue Graph

এই আর্কিটেকচারের ফলে Issue system একটা feedback loop তৈরি করবে:

```text
Plan
 ↓
Issue
 ↓
Agent
 ↓
PR
 ↓
CI
 ↓
Verification
 ↓
New Finding
 ↓
New Issue
 ↓
Agent
```

অর্থাৎ নতুন কাজের বড় অংশ system-এর নিজের observation থেকে তৈরি হতে পারে।

## 33. What We Remove

নতুন আর্কিটেকচারের লক্ষ্য unnecessary orchestration কমানো।

যেসব জিনিস শুধু Agent-to-Agent coordination-এর জন্য তৈরি হয়েছিল, সেগুলোকে পুনর্মূল্যায়ন করতে হবে:

```text
Heavy handoff schemas
In-memory mailbox
Swarm coordinator
Complex agent-to-agent messaging
Role-specific workflow engines
Duplicated orchestration state
```

তবে কোনো component শুধু "পুরনো" বলে delete করা যাবে না।

প্রথমে:

```text
Capability Ledger
 ↓
Actual usage
 ↓
Dependencies
 ↓
Replacement path
 ↓
Migration
 ↓
Removal
```

অর্থাৎ **capability loss নয়, orchestration simplification।**

## 34. New Minimal Control Architecture

শেষ পর্যন্ত target architecture অনেকটা:

```text
                 GITHUB / SOURCE OF TRUTH
                         │
              ┌──────────┴──────────┐
              │                     │
            Issues                 PRs
              │                     │
              └──────────┬──────────┘
                         │
                 CONTROL / SCRIPTS
                         │
       ┌─────────────────┼─────────────────┐
       ↓                 ↓                 ↓
    Claim/Slot       Event Engine       Scheduler
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ↓
                  Living Prompt
                         ↓
                   Agent Fleet
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
            Work       Evidence    PR
                         │          │
                         └────┬─────┘
                              ↓
                             CI
                              ↓
                     Group Verification
                              ↓
                     Audit / Breaker
                              ↓
                    New Issues if needed
                              ↓
                        Merge Train
```

## 35. The Three Automation Planes

### 1. Event Plane

> "কিছু ঘটেছে।"

```text
CI failed
PR changed
Issue completed
Group completed
Audit failed
```

→ immediate response.

### 2. Time Plane

> "সময় হয়েছে।"

```text
daily audit
weekly architecture check
periodic breaker
browser health
third-party health
```

→ create mission Issue.

### 3. Work Plane

> "কাজ আছে।"

```text
Issue
 ↓
Claim
 ↓
Agent
 ↓
Work
 ↓
Evidence
```

এই তিনটি plane একসাথে কাজ করবে।

*(PART II §40-এ এখানে চতুর্থ plane যোগ হয়েছে — Idle Plane।)*

## 36. Final SupremeAI Agent Philosophy

> **SupremeAI does not need an ever-growing collection of workflow-specific agents. It needs a stable fleet of specialized capabilities operating through a universal work protocol.**
>
> **Agents specialize in what they can do. Issues define what needs to be done. Groups define why related work belongs together. Priority defines urgency. AQL defines acceptance. Scripts coordinate ownership and scheduling. Events trigger immediate work. Time triggers recurring work. CI and governance enforce deterministic gates.**
>
> **The agent has freedom over how to solve the assigned problem; the Control Plane controls where, when, and within what boundaries it may act.**

### বাংলায়:

> **SupremeAI-এর লক্ষ্য বেশি বেশি ধরনের workflow-agent তৈরি করা নয়। লক্ষ্য হলো কিছু স্থিতিশীল specialized capability রাখা এবং তাদের একটি universal work protocol-এর মাধ্যমে পরিচালনা করা।**
>
> **Agent জানবে সে কী করতে পারে। Issue বলবে কী করতে হবে। Group বলবে কেন related কাজগুলো একসাথে। Priority বলবে কোনটা আগে। AQL বলবে কখন কাজ গ্রহণযোগ্য। Script ownership ও scheduling পরিচালনা করবে। Event তাৎক্ষণিক কাজ তৈরি করবে। Time recurring কাজ তৈরি করবে। CI ও Governance deterministic gate হিসেবে থাকবে।**
>
> **Agent কীভাবে সমস্যার সমাধান করবে সে বিষয়ে স্বাধীন; কিন্তু কোথায়, কখন এবং কোন সীমার মধ্যে কাজ করবে তা Control Plane নির্ধারণ করবে।**

## 37. One-Line Architecture

> **Specialized Agents + Issue-Centric Work + Group-Aware Verification + Event-Driven Automation + Time-Driven Missions + Deterministic CI/Governance**

সবচেয়ে ছোট operational loop:

> **Issue → Claim → Work → Evidence → Event/Verification → Next Issue**

*(PART II §47-এ এই one-line ও loop ডুয়াল-ট্র্যাক + কিউ-জিরো সেলফ-অডিটসহ হালনাগাদ হয়েছে।)*

---

# PART II — ADDENDUM: Dual-Track Issues, Idle Plane ও Expanded Fleet (§38–§47)

## 38. Dual-Track Issue System — Manual আর Agent আলাদা Queue

মূল নিয়ম:

> **প্রতিটি Issue-এর একটি `track` থাকবে — `manual` / `agent` / `hybrid`। Agent কখনো manual-track issue claim করতে পারবে না। Manual-track issue agent queue-র গণনায়ই ঢুকবে না।**

```yaml
# Issue-এর নতুন field
id: 1381
track: manual              # manual | agent | hybrid
track_reason: secret_rotation
required_human_action: GEMINI_API_KEY rotate
```

Track নির্ধারণের মানদণ্ড:

| Track | কখন | উদাহরণ |
|---|---|---|
| `manual` | credential/account/cost/আইনগত ক্ষমতা কেবল মানুষের হাতে | secret rotation (vault-doctor class), provider plan/cost decision, external account action, production certification চূড়ান্ত sign-off, constitution/rules amendment |
| `agent` | পুরোপুরি স্বয়ংক্রিয় সম্ভব | code fix, test, refactor, docs regen, CI repair, audit execution, adversarial run |
| `hybrid` | agent prepare → human decide → agent execute | baseline-entry approval, destructive migration, নতুন external dependency adoption |

### Implementation — শূন্য নতুন infrastructure

```text
labels: track:manual | track:agent | track:hybrid
+ acquire_work_slot.py-তে claim guard (track:manual দেখলে claim reject)
+ Control Tower dashboard-এ দুটি আলাদা view (owner / fleet)
```

### কেন দরকার (বাস্তব প্রমাণ)

vault-doctor issues (#1378–#1392 ক্লাস) মাসের পর মাস open থাকে — এগুলো agent পারে না, তাই agent queue-তে "লাটানো" থাকে এবং **"সব agent-কাজ শেষ হয়েছে কি?"** প্রশ্নের উত্তর ভুল দেখায়। Dual-track এলে agent queue-র শূন্য মানে **সত্যিই শূন্য**।

### Group-এর সাথে সম্পর্ক

এক Group-এ দুই track-এর issue থাকতে পারবে। কিন্তু `GROUP_COMPLETED` শুধু তখনই ফায়ার করবে যখন সব **agent-track** issue complete + verification pass হয়। Manual sign-off issue থাকলে সেটি merge-কে নয়, **certification-কে** block করবে (Group-এর শেষ human gate)।

## 39. Triage Capability — প্রতিটি Issue-এর দরজায় দাঁড়ানো প্রহরী

Issue যে দিক থেকেই আসুক (human, event engine, scheduler, audit, breaker) — ঢোকার আগে classify:

```text
New Issue
   ↓
Triage (rule-first, LLM-fallback শুধু ambiguous-তে)
   ├─ track:     manual | agent | hybrid
   ├─ priority:  P0–P3
   ├─ group:     assign / propose
   ├─ AQL:       আছে? না থাকলে generate বা জিজ্ঞেস
   ├─ dedup:     open issues-এর বিরুদ্ধে
   └─ template:  scope/constraints/evidence কাঠামো
   ↓
সঠিক queue-তে routed
```

### Rule-first heuristics (deterministic)

* secret-key নাম, "manual action needed", cost/plan keyword → `manual`
* code/test/docs path, CI fix ভাষা → `agent`
* approval-required / baseline-add ভাষা → `hybrid`
* শুধু ambiguous কেসে LLM fallback

### কেন script-first

Intake-এ ভুল হলে পুরো pipeline ভুল দিকে যায় — তাই এই দরজাটা যতটা সম্ভব deterministic হতে হবে।

## 40. চতুর্থ Automation Plane — Idle Plane (Queue-Zero)

§35-এর তিন plane-এর সাথে চতুর্থ:

| Plane | প্রশ্ন | Trigger | Output |
|---|---|---|---|
| Event | "কী ঘটল?" | CI fail / PR change / group complete | responsive issue |
| Time | "সময় হয়েছে?" | cron | mission issue |
| Work | "কে করবে?" | claim | work slot + evidence |
| **Idle** | **"সব শেষ হয়েছে?"** | **QUEUE_ZERO predicate TRUE** | **SYSTEM_AUDIT issue** |

### QUEUE_ZERO predicate — পাঁচটির সবগুলো TRUE হতে হবে

```text
1. agent-track claimable open issues == 0
   (manual-track এবং blocked-on-manual hybrid গণনায় আসবে না)
2. কোনো PR merge-train / queue:hold-এ pending নেই
3. main CI বর্তমান HEAD-এ green
4. artifact-regen শেষ run green/no-op (drift নেই)
5. কোনো agent-এর সক্রিয় lease/claim নেই
```

**৩–৪ কেন জরুরি:** red main বা stale artifact নিয়ে "সব শেষ" দাবি করা অর্থহীন। সেই state-এ Idle plane চুপ থাকবে — কাজটা Work plane-এর (CI fix issue ইতিমধ্যে event engine তৈরি করেছে)।

### Detection

Lightweight scheduled detector (Issue Ops-এর একই pattern) — প্রতি ~১৫ মিনিটে predicate check; TRUE হলে ঠিক **একটি** `SYSTEM_AUDIT` issue তৈরি। **Anti-flap:** এরপর re-arm হবে শুধু নতুন landing বা নতুন issue-তে।

## 41. Queue-Zero → স্বয়ংক্রিয় System Audit

> **Agent queue শূন্য হওয়া মানে "কাজ শেষ" নয় — মানে "প্রমাণ করার সময় এসেছে।"**

```text
QUEUE_ZERO event
   ↓
Issue তৈরি: [SYSTEM_AUDIT] full convergence audit
   (type: SYSTEM_VERIFICATION, priority: P1)
   ↓
Certifier/Auditor-capable agent claim করে
   ↓
Machine-verifiable audit sweep (A1–A10)
   ↓
findings → severity + dedup করা নতুন issues → Work plane আবার চালু
   ↓ (finding শূন্য)
CERTIFIED_STEADY_STATE + manual backlog report
```

### Audit sweep — প্রতিটি দফা machine-checkable

| # | দফা | যাচাই করে |
|---|---|---|
| A1 | CI truth | শেষ Kটি main run green; CI Doctor tracker issue-গুলো state-সঠিক (red থাকলে close হয়নি) |
| A2 | STATUS truth | STATUS_PROOF = PASS; প্রতিটি claim tree-reality-র সাথে মেলে |
| A3 | Artifact freshness | সব generated artifact byte-fresh; regen no-op |
| A4 | Gate wiring | rules.yml-এর প্রতিটি declared gate সত্যিই wired + enforced |
| A5 | Baseline hygiene | stale baseline entry নেই (topology/hardcode baselines) |
| A6 | Sentinel health | gate/sentinel নিজেরা bug-free — false positive নেই |
| A7 | PR/branch hygiene | stale branch, superseded/draft PR, orphan label |
| A8 | Security gates | topology, hardcoded-config, secret-scan — সব green |
| A9 | Docs truth | master index/lessons/reference বনাম tree |
| A10 | Manual backlog report | owner-কে গোছানো তালিকা: কী কী শুধু মানুষ পারে |

### Findings discipline

```text
• P0/P1 finding → সাথে সাথে আলাদা issue
• P2/P3 finding → একটি batched hygiene issue
• Dedup open issues-এর বিরুদ্ধে mandatory — audit নিজে issue-flood করতে পারবে না
• প্রতিটি finding-এ evidence link (Verification Gate-এর মতোই)
```

## 42. Convergence Loop — Idle মানে Certified

```text
Work plane: issue → triage → claim → work → evidence → PR → CI
      ↓
Group verification → merge train → landing
      ↓
agent queue == 0? ── না → পরের issue
      │ হ্যাঁ
      ↓
Idle plane: SYSTEM_AUDIT (A1–A10)
      ↓
finding আছে? ── হ্যাঁ → নতুন issues → Work plane (loop চালু)
      │ নেই
      ↓
CERTIFIED_STEADY_STATE
   • owner signal: "agent-কাজ শেষ + audit clean;
      বাকি শুধু manual backlog: [#1378, #1379, #1390, …]"
   • re-arm: পরের landing/event-এ
```

### লুপের গভীর অর্থ

> **System "আমি শেষ" দাবি করতে পারবে না যতক্ষণ না নিজের উপর পূর্ণ audit pass করে। Idle = certified; certified = প্রমাণিত।**

এটাই production certification (#1096) -এর **স্বয়ংক্রিয় অর্ধেক**: SYSTEM_AUDIT clean হলে Certifier evidence pack বানাবে (consecutive-green, runtime probe, CORS path, deploy consistency), চূড়ান্ত sign-off থাকবে manual-track issue হিসেবে — মানুষের হাতে।

### Learning tie-in

একই class-এর finding বারবার এলে (যেমন বারবার stale baseline) Knowledge capability pattern হিসেবে জমাবে → Time plane ওই class-এর নিয়মিত hygiene mission চালু করবে → root cause স্থায়ীভাবে বন্ধ। **Audit symptom ধরবে; Learning রোগ সারাবে।**

## 43. Expanded Fleet — ১০ থেকে ১৭ Capability

§5-এর justify-first নিয়ম মেনেই সম্প্রসারণ। নতুনগুলিতে ★:

| Capability | Responsibility | Trigger | Justify-first উত্তর (কেন আলাদা) |
|---|---|---|---|
| ★ Triage | intake classify — track/priority/group/AQL/dedup | Event: issue created | দরজার প্রহরী; deterministic script-first |
| ★ Certifier | certification evidence pack, runtime probe, consecutive-green proof | QUEUE_ZERO + manual | Auditor-এর certification-mission-এর evidence-specialization |
| ★ Sentinel | verification-tooling-এর নিজস্ব integrity — gate/sentinel-এর bug, false positive | Time + gate-anomaly event | gate-এর উপরে দাঁড়ায় — Auditor যাদের দিয়ে audit করে, তাদেরই audit |
| ★ Janitor | zero-debris — stale branch/label/baseline/PR/issue | Event: landing-এর পর + Time | OPS-09 janitor-এর fleet-level সাধারণ রূপ |
| ★ Ops/Reliability | watcher-of-watchers — CI Doctor, workflow নিজেরা সুস্থ কি না | Time + workflow-fail event | artifact-regen-dead class — infrastructure-এর infrastructure |
| ★ Release | merge-train driver — hold-release, batch landing, rollup | Event: GROUP_VERIFIED | deterministic script-first; Hard Rule 5-এর enforcement |
| ★ Knowledge | memory consolidation, lessons, pattern extraction | Event: issue close + Time | §30-এর বাস্তবায়ন — memory=knowledge, issue=work-state |

মোট ফ্লিট: আগের ১০ (§5) + নতুন ৭ = **১৭টি capability**।

### নোট

* **Capability ≠ instance** — এক agent-instance একাধিক capability বহন করতে পারে যদি lease/permission অনুমতি দেয়।
* Fleet বাড়ানোর default প্রশ্ন এখনও: **"existing capability + নতুন mission দিয়ে হয় না?"** — টেবিলের শেষ কলাম প্রমাণ যে প্রতিটি নতুন capability এই প্রশ্ন পার হয়ে এসেছে।

## 44. Updated Master Diagram

```text
                    GITHUB / SOURCE OF TRUTH
                            │
              ┌─────────────┴─────────────┐
              │                           │
     Issues (dual-track)                PRs
     ┌──────┴──────┐                      │
     │             │                      │
 manual-track   agent-track               │
 (owner view)        │                    │
                Triage ── classify ──┐    │
                    track/priority/  │    │
                    group/AQL/dedup  │    │
                     ┌───────────────┘    │
                     ↓                    │
              CONTROL / SCRIPTS           │
                     │                    │
      ┌──────────┬───┴──────┬───────────┐ │
      ↓          ↓          ↓           ↓ │
  Claim/Slot  Event      Scheduler  QUEUE-ZERO
      │      Engine      (Time)     Detector
      │          │          │           │ │
      └──────────┴────┬─────┴───────────┘ │
                     ↓                   │
                Living Prompt             │
                     ↓                   │
                Agent Fleet ←─────────────┘
                     ↓
           Work → Evidence → PR → CI
                     ↓
             Group Verification
                     ↓
             Merge Train → Landing
                     ↓
             [agent queue == 0?]
              না → পরের Issue (Work plane)
              হ্যাঁ → SYSTEM_AUDIT (Idle plane)
                        ↓
          findings → নতুন Issues → Work plane ↺
          clean → CERTIFIED_STEADY_STATE
                  + manual backlog report
```

## 45. Real-World Grounding — আজকের main কেন এই design-কে চিৎকার করে বলছে

| Design element | বাস্তব প্রমাণ (main @ 25792401, 2026-09-28) |
|---|---|
| `manual` track দরকার | #1378–#1392 vault issues agent-এর পৌঁছানোর বাইরে, তবু agent queue-তে লাটানো |
| Audit A1 (CI truth) দরকার | CI Doctor red থাকা অবস্থায় #2351 auto-close করে ফেলেছিল |
| Audit A2 (STATUS truth) | STATUS_PROOF = FAIL (registered_routes 761 বনাম বাস্তব 862) |
| Audit A3 (artifact fresh) | artifact-regen প্রতিটি main commit-এ red (#2344) |
| Audit A4 (gate wiring) | self_merge / test_guard / post_merge_watch — ৩টি gate declared কিন্তু unwired |
| Audit A5 (baseline hygiene) | ৩টি stale baseline entry + ৫টি untracked identifier leak |
| Audit A6 (sentinel health) | QA parity sentinel-এর split-router blind spot — ৫টি false-positive HIGH |
| Predicate ৩–৪ জরুরি | main বর্তমানে red — এই state-এ queue-zero audit চালালে মিথ্যা রিপোর্ট আসত |

অর্থাৎ addendum-এর প্রতিটি নিয়ম কোনো না কোনো বাস্তব failure থেকে উৎসারিত — কল্পনা নয়, প্রমাণ।

## 46. Updated Philosophy (§36-এর সাথে যোগ)

> **Issues carry a track — manual work never blocks or pollutes agent work, and agent work never waits behind human decisions. When the agent track empties, the system does not rest — it proves itself: an automatic audit verifies that "empty" means "done, true, and certified," not "nobody looked." Only a clean audit grants the system its idle state, and even then it hands the owner a precise list of what only a human can do.**

### বাংলায়:

> **Issue বহন করবে track — manual কাজ কখনো agent queue দূষিত করবে না, agent কাজ কখনো মানুষের সিদ্ধান্তের পেছনে আটকে থাকবে না। Agent track খালি হলে system বিশ্রাম নেয় না — নিজেকে প্রমাণ করে: স্বয়ংক্রিয় audit যাচাই করে "খালি" মানে "শেষ, সত্য এবং certified" — "কেউ তাকায়নি" নয়। শুধুমাত্র clean audit system-কে idle দেয়; এবং তখনও সে owner-কে দেয় একটি নির্ভুল তালিকা — কী কী শুধু মানুষই পারে।**

## 47. Updated One-Line Architecture

> **Specialized Agents + Dual-Track Issues + Issue-Centric Work + Group-Aware Verification + Event/Time/Idle-Driven Automation + Queue-Zero Self-Audit + Deterministic CI/Governance**

সবচেয়ে ছোট operational loop:

> **Issue → Triage → Claim → Work → Evidence → PR → CI → Group Verification → Merge Train → Landing → Queue-Zero → Self-Audit → (New Issues ⟳ | Certified Idle ✓)**

---

*AIBRAIN-02 · Agent System 2.0 Master Plan · সংস্করণ ১.০ · 2026-09-28 · [ARCH-10](ARCH-10-UNIVERSAL-ENGINE-MASTER-PLAN-GROUP-STAGING-RULE-ENGINE-BATCH-TRAIN-RED-TEAM.md)-এর সাথে পড়ুন*
