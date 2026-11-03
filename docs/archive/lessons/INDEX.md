# Lessons Index — শেখা ও বেঁচে থাকার প্যাটার্ন

> প্রতিটি এন্ট্রি: ঘটনা → মূল কারণ → টেকসই প্যাটার্ন। বিস্তারিত `worklogs/worklog.md`-এ।

## L-001 Job-log 401 (Azure redirect)
- **ঘটনা:** GitHub Actions log endpoint 401।
- **কারণ:** লগ Azure blob-এ redirect; cross-origin redirect-এ Authorization হেডার ঝরে যায়।
- **প্যাটার্ন:** NoRedirect handler → Location ধরে ম্যানুয়াল ফলো।

## L-002 `Refs` বনাম `Closes` (#15 stale-open)
- **ঘটনা:** PR #16 merge হলেও issue #15 খোলা রইল।
- **কারণ:** merge commit-এ `Refs #15` — auto-close কীওয়ার্ড নেই।
- **প্যাটার্ন:** auto-close চাইলে merge commit-এই `Closes #N`।

## L-003 Sandbox reset playbook
- **প্যাটার্ন:** ① `mint_token.py` → App-install token ② Infisical universal-auth login (inline self-contained) → PAT → /tmp/pay_pat (0600) ③ askpass স্ক্রিপ্ট (0700) ④ fork re-clone (--filter=blob:none) ⑤ এখন: worklog-এর স্থায়ী মিরর এই রিপোতেই।

## L-004 Evaluator PENDING race
- **প্যাটার্ন:** gh-shim দিয়ে লোকাল evaluator; owner squash-merge; bot-head-এ run-approve API।

## L-005 Claim-chain চার-খণ্ড
- Template body: `## Summary` + `Refs #N` + Rollback; conventional title; priority tier; `Touching files:` exact marker।

## L-006 Workflow-ID দুর্ঘটনা (Grep নাম-মিল)
- **প্যাটার্ন:** একই নামের workflow → grep নয়, workflows list endpoint থেকে exact ID।

## L-007 CI লাল = সবার আগে
- main লাল থাকলে integration-CI/নতুন ফিচার অর্থহীন (§12 gate discipline)।

## L-008 Fork-এ upstream workflow-এর secret (vault→sealed-box)
- **ঘটনা:** fork-এ secret-শূন্যতা — upstream-sync-এ secret আসে না; ৫ লাল চেকের মূল কারণ।
- **প্যাটার্ন:** vault → GitHub sealed-box (PyNaCl) দিয়ে secret PUT; প্রথম 422-শিক্ষা: key_id + Content-Type আবশ্যক।

## L-009 LFS-pointer mirror clone
- **প্যাটার্ন:** LFS-pointer-যুক্ত mirror clone-এ সবসময় `GIT_LFS_SKIP_SMUDGE=1`।

## L-010 নতুন টেমপ্লেট-গেট চুক্তি (#4139)
- `## Linked Issue` আবশ্যক; Verification Gate → `## Test Evidence` (passed/ok./✓ — ৪০+ অক্ষর); secrets-classification গেট; **body-edit-এ গেট re-run হয় না → empty-commit push-ই trigger**; Touching files-এ প্রতিটি বিচ্যুত-ফাইল আগে-ঘোষণা।

## L-011 GitHub incident retry-loop
- **ঘটনা:** ~৬ মিনিট write-operations অচল (POST 500 + push rejected)।
- **প্যাটার্ন:** write-অপারেশনে সবসময় retry-loop রাখা।
