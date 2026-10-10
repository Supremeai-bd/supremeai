# Bridge — public → private work pipeline (v1)

**অর্থ:** public agents (`paykaribazaronline/supremeai-open`) → private codebase
(`paykaribazaronline/supremeai`) — কোনো private access ছাড়াই, পূর্ণ gate-শৃঙ্খলায়।

```
AGENT (public)                          BRIDGE (private, fail-closed)
─────────────────                       ──────────────────────────────
patch branch bridge/<task-id>   ──────▶  validate task_id → dedup →
work-order issue                        diff size/file caps → secret scan →
(label bridge:queued)                   forbidden-path check
                                          ├─ protected path → bridge:admin-review
                                          ├─ secret hit     → bridge:rejected
                                          └─ clean → private intake issue +
                                                     bridge-land/<task-id> branch +
                                                     gated PR (canonical template)
                                                → constitutional gates decide
                                        status → public issue (sanitized) + labels
PR merged / closed  ──────────────▶     sync: bridge:landed | bridge:rejected
```

## অপারেটর চুক্তি (machine contract)

| নিয়ম | মান |
|---|---|
| Task ID | `bridge-YYYYMMDD-<slug>` (lowercase-hyphen) |
| Patch | public repo-র branch, diff base = public `main` |
| Size caps | ≤ 200 KB diff, ≤ 30 files |
| Secret scan | 10 families (ghs_/ghp_/github_pat_/sk-/AKIA/xox/AIza/PEM/literal-secret/redis-url) → reject |
| Protected paths | `.github/`, `docs/ledger/`, `docs/master_docs/`, `prisma/`, `*credential*`, `*.pem/.key/.p12`, `.env*` → admin-review |
| Dedup | private intake issue marker `<!-- bridge-task: <id> -->` (fail-closed on unknown state) |
| Landing | শুধুমাত্র constitutional gates — bridge কখনো merge করে না |
| Reporting | public issue-তে sanitized কমেন্ট (token/secret কখনো যায় না) |
| Retry | আগের রান push করা `bridge-land/<task-id>` branch থাকলে সেটিকেই base করে fast-forward retry — force-push নয়, একই patch দুইবার commit নয় (E4) |
| Pagination | sync/list সব GitHub list-call `Link: rel="next"` ফলো করে; cap-এ পৌঁছালে fail-honest, নীরব truncation নয় (E5) |

## Components

- `scripts/bridge/bridge_intake.py` — intake (validate+apply) + sync (lifecycle report)
- `.github/workflows/bridge-intake.yml` — schedule `13,43 * * * *` (৩০ মিনিটের ছন্দ,
  off-peak :13/:43 স্লট — issue #52) + `workflow_dispatch` (`mode`: `both` | `intake`
  | `sync`, `type: choice`); token = vault `GITHUB_PAT_PAYKARIBAZARONLINE`
  runtime-fetched via `INFISICAL_*` (শূন্য repo-secret, archive-mirror.yml-এর প্রমাণিত
  pattern)। Run fail-fast (`set -euo pipefail`) + একটাই invocation —
  `python scripts/bridge/bridge_intake.py "$MODE"` (স্ক্রিপ্টই mode ভ্যালিডেট করে ও
  intake→sync rc প্রোপাগেট করে); `cancel-in-progress: false` (মাঝপথে cancel হলে
  orphan branch তৈরি হয়ে retry বান হয়ে যায় — তাই run শেষ হোক), job
  `timeout-minutes: 45`।
- `.github/scripts/constitution/tests/test_bridge_automation_contract.py` — workflow
  hardening + watchdog name-coupling guard (E-series)
- `tests/test_bridge_intake.py` — pure-function unit battery

## Design invariants (কেন এভাবে)

1. **Public main কখনো নোংরা হয় না** — agents শুধু branch + issue ব্যবহার করে; main-এ লেখা
   শুধু federation mirror CI-র একচেটিয়া অধিকার।
2. **Patch = data, code নয়** — patch private repo-র ভেতরে গিয়েই কোড হয়, যেখানে পূর্ণ
   gate battery (template/scope/lease/evaluator/merge gate) চলে। Agent-এর private
   write-access লাগে না।
3. **Verifier ≠ implementer অটুট** — landing সিদ্ধান্ত evaluator+owner; bridge শুধু বাহক।
4. **Ledger chain সংরক্ষিত** — commit + intake issue-তে agent attribution থাকে, তাই
   Task Outcome Ledger (#4271) রেকর্ড এই কাজের জন্যও সম্পূর্ণ হয়।
