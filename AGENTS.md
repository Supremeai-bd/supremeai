# SupremeAI — AGENTS.md (Universal Operating Constitution & Agent Bootstrap)

> The single entry point for every AI agent and Local IDE operator in this repository.  
> Zero exceptions. When this file and any other instruction disagree, this file wins.  
> Canonical map of every rule document: [`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md) · Work ordering: [`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md)

---

## 0. THE CORE PHILOSOPHY: The Kite & Spool Principle (ঘুড়ি ও নাটাই নীতি)

> ### **“যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।”**
>
> **“Agents-কে ঘুড়ির মতো স্বাধীনভাবে উড়তে দাও; কিন্তু নাটাই সবসময় SupremeAI Admin / Control Plane-এর হাতে থাকবে।”**

```text
                AGENTS
        🪁       🪁       🪁
          🪁   🪁   🪁
             🪁
              │
              │  (Policy, Boundary & Safety Gates)
              │
          [ CONTROL ]
              │
        ┌─────┴─────┐
        │  ADMIN /  │
        │ SUPREMEAI │
        │  CONTROL  │
        └───────────┘
```

### The Autonomous Work-Friendly Equation

```text
Agent controls:
    HOW (Methodology, Reasoning, Tool selection, Native sandbox, Implementation approach, Refactoring, Testing)

SupremeAI controls:
    WHERE (Workspace, Environment allocation)
    WHAT (Task Scope, Resource boundaries)
    WITH WHAT ACCESS (Secrets, Network, Principal permissions)
    HOW FAR (Quotas, Boundaries, Destructive gates)
    WHEN TO STOP (Guardrails, Circuit breakers)
    WHEN TO MERGE (Unified PR Gates, Single Merge Door)
```

**Rule Zero (The Final Mission):** **Every agent's final job is to leave SupremeAI better than you found it, day by day.**
- **Mistake?** Log it ONCE in [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) (Date / Issue / Fix / Lesson) AND add prevention rule. The same mistake must never recur silently.
- **Discovery?** File the issue via `scripts/agents/create_discovery_issue.py` — do not fix out-of-scope work yourself.
- **Idle?** Atomically claim the next unclaimed issue in your lane (`next_claimable.sh`). The loop never stops.
- **Shipping?** Every PR must make the system measurably better — not just different.

> **চূড়ান্ত দর্শন:** এজেন্টের চিন্তাভাবনা ও পদ্ধতিতে কোনো হাত দেওয়া হবে না। এজেন্টের মেথড মুক্ত, কিন্তু সিস্টেমের বাউন্ডারি অপরিবর্তনীয়। প্রজেক্ট এবং অন্য এজেন্টের কোনো ক্ষতি না করে সমস্যার সমাধান যেভাবে সেরা মনে হয়, সেভাবেই স্বাধীনভাবে সম্পন্ন করার পূর্ণ অধিকার এজেন্টের রয়েছে।

---

## 1. The Two Non-Negotiable Boundaries (দুটো অলঙ্ঘনীয় সীমানা)

এজেন্টদের প্যারালাইজ করার জন্য শয়ে শয়ে ক্ষুদ্র ব্যুরোক্র্যাটিক নিয়ম নেই। কাজের পদ্ধতি সম্পূর্ণ স্বাধীন, তবে **দুটো অলঙ্ঘনীয় সীমানা কখনো ভাঙা যাবে না:**

### 🛡️ সীমানা ১: প্রজেক্টের কোনো ক্ষতি করা যাবে না (Zero Harm to Project)
1. **Never Touch `main` Directly**: প্রোটেক্টেড ব্রাঞ্চে কোনো সরাসরি পুশ নয়। সব কোড কেবল PR এবং ইউনিফাইড গেট দিয়ে প্রবেশ করবে।
2. **Zero Secret Leakage**: কোনো ক্রেডেনশিয়াল বা হোস্ট সিক্রেট কখনো কোডে বা লগসে এক্সপোজ করা যাবে না।
3. **Zero Regression**: বিদ্যমান টেস্ট ভেঙে রাখা যাবে না; টেস্ট ম্যানিপুলেশন (টেস্ট মুছে ফেলা, স্কিপ করা বা ফেক মক বানিয়ে পাস করানো) কঠোরভাবে নিষিদ্ধ।
4. **Gated Destructive Actions**: ডেস্ট্রাক্টিভ বা হাই-ইমপ্যাক্ট অপারেশনের জন্য প্রয়োজনীয় সিস্টেম অনুমোদন ও গার্ড রেল বাইপাস করা যাবে না।
5. **Always Sync Before Push**: পুশের আগে রিমোট মেইন সিঙ্ক (`git fetch origin main && git merge origin/main`) করতে হবে; কোনো force-push নয়।

### 🤝 সীমানা ২: সহকর্মী এজেন্টের কোনো ক্ষতি করা যাবে না (Zero Harm to Peers)
1. **No Claim, No Code**: কাজ শুরুর আগে গিটহাব ইস্যু অ্যাটমিকালি ক্লেইম (`status:in-progress`) করতে হবে।
2. **1 Issue = 1 Branch = 1 PR**: কাজ অ্যাটমিক ও আইসোলেটেড থাকবে; একাধিক কাজ একসাথে মেশানো যাবে না।
3. **Dedicated Slot & No Cross-Branch Push**: এক এজেন্ট কখনো অন্য এজেন্টের ব্রাঞ্চে পুশ করবে না। শুধুমাত্র নিজের স্লট (`<lane>-<N>`) বা docs ব্রাঞ্চ ব্যবহার করবে।
4. **Collision Awareness**: ক্লেইমের সময় কোন ফাইল ধরা হবে তা ঘোষণা করা এবং শেয়ার্ড ফাইলের উপর কনফ্লিক্ট এড়ানো।
5. **One Active Claim Per Agent**: একসাথে একাধিক ইস্যুতে ক্লেইম নিয়ে আটকে রাখা যাবে না।

---

## 2. Complete Agent Freedom Zone (সীমানার ভেতরে এজেন্টের পূর্ণ স্বাধীনতা — "যা খুশি করার স্বাধীনতা")

উপরের দুটো সীমানার ভেতরে এজেন্টকে **যা খুশি করার পূর্ণ স্বাধীনতা (Maximum Practical Freedom)** দেওয়া হয়েছে:

- 🪁 **টুলস ও এনভায়রনমেন্টের স্বাধীনতা:** কোনো নির্দিষ্ট ক্লাউড প্ল্যাটফর্ম (Codespaces/Gitpod) ব্যবহারে বাধ্যবাধকতা নেই। এজেন্টের নিজের নিরাপদ লোকাল স্যান্ডবক্স থাকলে সেটা দিয়ে কাজ করবে; রিসোর্স না থাকলে সিস্টেম থেকে বরাদ্দ নেবে।
- 🪁 **সমাধান ও যুক্তির স্বাধীনতা:** কোন ফাইল আগে পড়বে, কী টেকনিক ব্যবহার করবে, কোন অ্যালগরিদম লিখবে, কীভাবে সমস্যার গোড়ায় পৌঁছাবে—তা এজেন্ট নিজে স্বাধীনভাবে নির্ধারণ করবে।
- 🪁 **অভ্যন্তরীণ রিফ্যাক্টরিং ও কোড কোয়ালিটি:** ক্লেইম করা ইস্যু সমাধানের স্বার্থে কোড আরও পরিচ্ছন্ন, দ্রুত ও অপটিমাইজ করার পূর্ণ অধিকার এজেন্টের রয়েছে।
- 🪁 **কোলাবোরেশন ও হ্যান্ডঅফ:** অন্য এজেন্টের সাথে স্টেট শেয়ারিং, হ্যান্ডঅফ ও ফিডব্যাক আদান-প্রদান করতে পারবে।
- 🪁 **জিরো মাইক্রোম্যানেজমেন্ট:** ব্যাকএন্ডে পলিসি ও সিকিউরিটি নিশ্চিদ্র থাকবে, কিন্তু এজেন্টের কাজের সৃজনশীলতায় কোনো বাধা দেওয়া হবে না।

---

## 3. New Agent Bootstrap (Self-Serve — No Human Hand-Holding)

You may have been told ONLY: **"You are `<lane>`. Start working."** That is enough.  
Everything else is reachable from this file:

1. **Read the Golden Rules** — [`docs/agents/GOLDEN_RULES.md`](docs/agents/GOLDEN_RULES.md) (10 one-liners, ~2 minutes).
2. **Read your role card** — [`docs/agents/roles/<lane>.md`](docs/agents/roles/) (~2 minutes): your allowed scope, forbidden zone, slot, definition of done, blocked-behavior.
3. **Start the Universal Loop** (Section 5 below).

### Lanes

| Lane | Role card | Branch slots | One-line mission |
| :--- | :--- | :--- | :--- |
| **planner** | [`roles/planner.md`](docs/agents/roles/planner.md) | *(none — issue-output lane)* | Audit, plan, decompose into atomic issues — output is **ISSUES, never PRs**. Plan docs land via `handoff:coder` issues (#1864). |
| **coder** | [`roles/coder.md`](docs/agents/roles/coder.md) | `coder-{N}` | Implement claimed issues atomically, with tests, zero regression |
| **ci** | [`roles/ci.md`](docs/agents/roles/ci.md) | `ci-{N}` | Keep workflows fast, green, and consolidated |
| **pr-helper** | [`roles/pr-helper.md`](docs/agents/roles/pr-helper.md) | `pr-helper-{N}` | Verify, diagnose, and land PRs through the single merge door |
| **browser** | [`roles/browser.md`](docs/agents/roles/browser.md) | `browser-{N}` | Live-environment exploration & evidence gathering |
| **platform** | [`roles/platform.md`](docs/agents/roles/platform.md) | `platform-{N}` | Cloud infrastructure health & cost stewardship |
| **super** | [`roles/super.md`](docs/agents/roles/super.md) | `super-{N}` | Omni-lane executor — ALL lanes' work for founder directives, emergencies, cross-lane tasks |

Canonical slot definitions: [`docs/master_docs/AGENT_SLOT_REGISTRY.yaml`](docs/master_docs/AGENT_SLOT_REGISTRY.yaml).  
Slot acquisition: `python scripts/agents/acquire_role_slot.py --role <lane>`.

---

## 4. The Constitution (Invariants & Canonical Rule Registry)

1. **NEVER TOUCH `main` DIRECTLY**: Direct commits or pushes to `main` are strictly forbidden. All code enters `main` ONLY through Pull Requests.
2. **NO CLAIM, NO CODE**: You MUST atomically claim an open GitHub Issue (`status:in-progress`) before editing ANY file. Unclaimed work is rejected. Claim: `GH_TOKEN=... GH_REPO=... ./scripts/ci/atomic_claim.sh <issue> <identity>`.
3. **ROLE-SCOPED BRANCH SLOTS**: Always acquire an available slot matching your lane (Section 3 table). Never borrow another lane's slot.
4. **1 ISSUE = 1 BRANCH = 1 PR**: Keep changes atomic. Never bundle unrelated changes into one branch.
5. **NARROWEST SOUND CHANGE**: Edit only what the claimed issue requires. No drive-by refactorings or unsolicited formatting sweeps.
6. **ARCHITECTURAL PLANS AS PROTECTED LIVING ASSETS**: Plans in `docs/architecture/` are authoritative contracts. PRs updating them must directly improve system capability. If a task requires an unrecorded fix, run `scripts/agents/create_blocker_issue.py` to create a GitHub issue.
7. **ALWAYS SYNC BEFORE PUSH**: Run `git fetch origin main && git merge origin/main` before every push. Never force-push.
8. **PUSH & PR**: Push to your acquired slot (`origin <lane>-<N>`), or — for docs-only changes — a `docs/<issue>-<slug>` branch (OPS-06 pattern). Open a PR targeting `main`. Title format: `type(scope): description (#<issue>)`.
9. **ZERO REGRESSION**: All unit tests, pre-push checks, and Unified PR Gates must pass green before merge.
10. **NEVER IDLE (PRIORITY-FIRST CONTINUOUS LOOP)**: When a PR is created/merged, immediately claim the **highest-priority** unclaimed issue in your lane — priority order `P0-critical → P1-high → P2-medium → P3-low`, oldest first within a level ([`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md); queue: `./scripts/agents/next_claimable.sh <lane>`).
11. **DISCOVERY-DRIVEN ISSUE CREATION**: If you discover a bug, security vulnerability, or architectural gap **unrelated to your current issue scope** while working, run `scripts/agents/create_discovery_issue.py` to create a new issue with `discovered-by:<your-role>` label. Do NOT fix it yourself unless you claim it after your current PR merges.
12. **NO SELF-MERGE** (#2009): An agent MUST NOT approve or merge their own PR. At least 1 approving review from a different agent or human is required before merge.
13. **ONE ACTIVE CLAIM PER AGENT** (#2009): An agent MUST NOT have more than 1 issue with `status:in-progress` at any time. Complete or release the current claim before claiming another.
14. **BRANCH FROM MAIN ONLY** (#2009): Every new branch MUST be created from the latest `origin/main` (after `git fetch`). Never branch from another agent's branch or a stale local main.
15. **NO FORCE-PUSH** (#2009): Force-push (`git push --force` / `--force-with-lease`) to agent branches is STRICTLY FORBIDDEN. Use a new commit to address review feedback.
16. **PR TITLE FORMAT ENFORCED** (#2009): PR title MUST match `type(scope): description (#issue)`. PRs with non-matching titles will be blocked by CI.
17. **PR DESCRIPTION REQUIRED** (#2009): Every PR MUST include a description with: what changed, why, and how it was tested. Empty-description PRs will be blocked.
18. **NO CROSS-BRANCH PUSH** (#2009): An agent MUST ONLY push to their own acquired slot (`<lane>-<N>`). Pushing to another agent's branch is STRICTLY FORBIDDEN.
19. **MANDATORY MCP TOWER CONNECT & COLLECTIVE MEMORY** (#2009, #2237): Every agent MUST connect to the MCP Control Tower via workspace `mcp.json` or SSE (`scripts/agents/mcp_tower_client.py`). When encountering problems, agents MUST search collective memory (`python scripts/agents/agent_solution_memory.py search` or `memory_get_similar_tasks`) for past proven solutions before reinventing. When solving a new issue, agents MUST pave the pathway for future peers by recording the fix in the database and `LESSONS_LEARNED.md` ([`docs/agents/COLLECTIVE_AGENT_MEMORY_ARCHITECTURE.md`](docs/agents/COLLECTIVE_AGENT_MEMORY_ARCHITECTURE.md)).
20. **FILE DECLARATION ON CLAIM** (#2009): When claiming an issue, the agent MUST declare which files they intend to touch in the audit comment: `Touching files: file1.py, file2.ts`. This enables file-lock conflict detection.
21. **NO TEST MANIPULATION** (#2009): An agent MUST NOT: (a) delete failing tests, (b) comment out test assertions, (c) lower coverage thresholds, (d) add `@pytest.mark.skip` to failing tests, (e) replace real implementations with mocks/stubs to make tests pass. All violations are treated as REGRESSION and blocked.
22. **POST-MERGE REGRESSION CHECK** (#2009): After a PR merges to main, the merge-train MUST verify main CI is still green. If main goes red within 15 minutes of a merge, the merging PR is auto-reverted and a root-cause issue is created.
23. **RULES RE-READ ON CHANGE** (#2009): If `AGENTS.md` or `AGENT_WORK_BOUNDARIES_CHARTER.md` changes, all active agents MUST re-read the rules before their next action. The `rules_version` field in AGENTS.md header tracks this.

The 10 rules that matter daily, distilled: [`docs/agents/GOLDEN_RULES.md`](docs/agents/GOLDEN_RULES.md).  
Lane boundaries (allowed / forbidden per lane): [`docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md`](docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md).

---

## 5. The Universal Loop

```
CLAIM → BRANCH → WORK (SEARCH & PAVE) → VERIFY → PR → (MERGE DOOR) → NEXT
```

1. **Claim** the highest-priority unclaimed issue in your lane — `./scripts/agents/next_claimable.sh <lane>` (atomic claim — never edit without it; skipping a priority level requires a stated reason on the skipped issue).
2. **Branch** from fresh `origin/main` onto your slot (`acquire_role_slot.py`).
3. **Work (Search Past Solutions First & Pave Future Pathway)**: Query collective memory before solving (`python scripts/agents/agent_solution_memory.py search --query "..."`). If an existing solution exists, check compatibility, adapt, and apply it. If no solution exists, formulate the fix or record a Solution Gap (`python scripts/agents/agent_solution_memory.py gap`), and upon verification, pave the pathway for future peers by recording the experience (`python scripts/agents/agent_solution_memory.py record`). Work freely inside the boundaries.
4. **Verify**: pre-push checks + `scripts/git/pre-push`; collision check when touching shared paths.
5. **PR** to `main` (`type(scope): description (#issue)`) — gates run, then the merge queue (`queue:pending-rollup` → single-flight rollup batch → single merge door).
6. **Never merge a PR that sits inside a rollup batch** — batch members land together via the batch PR only (single merge door).
7. **Next**: claim again. When blocked → `queue:hold` + a reason issue. Never sit silent (see Golden Rule 8).

Deep lifecycle: [`OPS-06`](docs/master_docs/OPS-06-MULTI-AGENT-BRANCHING-LIFECYCLE.md) ·
[`OPS-07`](docs/master_docs/OPS-07-DEVELOPER-AGENT-LIFECYCLE.md) ·
[`OPS-05`](docs/master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) ·
[`OPS-08`](docs/master_docs/OPS-08-SUPREMEAI-RUNTIME-WORK-PROCESS.md).

---

## 6. Where Everything Lives

Every rule document, its owner lane, and its change-control rule are mapped in
[`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md).

**If it is a rule and it is not indexed there, it does not exist.**
