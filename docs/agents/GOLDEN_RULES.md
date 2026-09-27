# SupremeAI — Golden Rules

> **The 8 rules that keep the ecosystem safe.** Easy to read, easy to follow, zero confusion.
> One line each — the deep document behind every rule is one click away.
> Read once at bootstrap; re-read whenever unsure. (Charter reference: `AGENTS.md` §0–§2.)

> **বাংলা সারমর্ম:** নিচের ৮টি নিয়ম মানলে কোনো এজেন্ট আর কখনো সিস্টেম নষ্ট করতে পারবে না — ভুল একবারই হবে, শেখা স্থায়ী হবে, আর প্রতিটি এজেন্টের কাজ হবে সিস্টেমকে দিনদিন ভালো করা।

| # | Rule | বাংলা | Deep doc |
| :--- | :--- | :--- | :--- |
| 1 | **MISSION FIRST** — your final job is a better system every day: mistake → log once + prevention; discovery → issue now; idle → **highest-priority** issue in your lane (`next_claimable.sh`). | চূড়ান্ত কাজ: সিস্টেমকে প্রতিদিন ভালো করা; অলস থাকলে সর্বোচ্চ-priority কাজ | [`AGENTS.md` §0](../../AGENTS.md) · [Priority policy](ISSUE_PRIORITY_POLICY.md) |
| 2 | **NO CLAIM, NO CODE** — never edit a file without an atomically claimed issue (`status:in-progress`). | দাবি ছাড়া কোড নয় | [`AGENTS.md` §2.2](../../AGENTS.md) |
| 3 | **1 ISSUE = 1 BRANCH = 1 PR** — atomic changes only; nothing rides along. | এক ইস্যু, এক ব্রাঞ্চ, এক PR | [`AGENTS.md` §2.4](../../AGENTS.md) |
| 4 | **STAY IN YOUR LANE** — your [role card](roles/) is the contract; allowed/forbidden is not a suggestion. Unsure? File an issue — do not cross. | নিজের লেনে থাকো | [Charter](AGENT_WORK_BOUNDARIES_CHARTER.md) |
| 5 | **NEVER BREAK MAIN** — all change flows through the single merge door, green gates first; a PR inside a rollup batch is NEVER merged directly. | main কখনো ভাঙবে না | [Charter](AGENT_WORK_BOUNDARIES_CHARTER.md) · [OPS-05](../master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) |
| 6 | **SYNC BEFORE PUSH, NEVER FORCE-PUSH** — `git fetch origin main && git merge origin/main` before every push. | পুশের আগে sync, force-push কখনো নয় | [`AGENTS.md` §2.7](../../AGENTS.md) |
| 7 | **A MISTAKE HAPPENS ONCE** — every error gets a `LESSONS_LEARNED.md` entry + a prevention rule (who / why / how-prevented). Auditor duty. | ভুল একবারই — শিক্ষা স্থায়ী | [`LESSONS_LEARNED.md`](../../LESSONS_LEARNED.md) |
| 8 | **BLOCKED → HOLD + REASON ISSUE** — never sit silent: `queue:hold` label + a GitHub issue carrying the reason and the exact unblock action. | আটকে গেলে কারণ-সহ ইস্যু | [Merge-train](../master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) |
| 9 | **NO SELF-MERGE, NO FORCE-PUSH, NO TEST CHEATING** — don't approve your own PR; don't force-push; don't delete/skip/mock tests to pass CI. These are the three fastest ways to destroy trust. | নিজের PR নিজে merge নয়; force-push নয়; test নষ্ট করে CI সবুজ নয় | [`AGENTS.md` §2.12, §2.15, §2.21](../../AGENTS.md) · [#2009](https://github.com/SaifulHaqueNiloy/supremeai/issues/2009) |
| 10 | **CONNECT TO MCP TOWER, DECLARE YOUR FILES** — connect at startup + heartbeat every 45s; declare which files you'll touch on claim so others don't collide. | MCP Tower-এ connect করো, কোন ফাইল ধরবে বলো | [`AGENTS.md` §2.19, §2.20](../../AGENTS.md) · [#2009](https://github.com/SaifulHaqueNiloy/supremeai/issues/2009) |

---

## Why only 10?

Because rules that are short get followed. Everything deeper — slot acquisition CAS,
branch naming, PR gates, merge-train batching, handoff schema — is **mechanics**, not
golden rules, and lives one click away in the [Rules Index](RULES_INDEX.md).

**If you remember nothing else:** *claim it, scope it to your lane, prove it green,
ship it through one door — and leave the system better than you found it.*

> **Rules #9-#10 added by #2009** (super agent, auditor-driven constitution update).
> Full violation matrix: [#2004](https://github.com/SaifulHaqueNiloy/supremeai/issues/2004).
