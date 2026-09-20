# Self-Approval Policy (GAP-02 fix)

> **Document ID:** SELF-APPROVAL · **Status:** Active · **Version:** 1.0 (2026-09)
> **Related Invariants:** SG-03 (Explicit Auth), SG-11 (Bootstrap Trust)
> **Related GAP:** ARCH-GAP-01 GAP-02

## 🎯 Problem

GitHub prevents users from approving their own PRs. SupremeAI submits PRs as `SaifulHaqueNiloy` (using the canonical `GITHUB_TOKEN`), but PR Helper also uses the same token. This means **SupremeAI's own PRs can NEVER be auto-approved** — `gh pr review --approve` returns a 403 error.

## 📋 Current Behavior (PR Helper Step 5)

```yaml
- name: Approve PR (non-fatal when author == token owner)
  run: |
    gh pr review "$PR" --approve \
      && echo "approved" \
      || echo "::notice::Auto-approve skipped (own PR বা branch protection policy) — শুধু classification comment যথেষ্ট।"
```

- ✅ Non-fatal: PR Helper Step 5 does NOT fail when self-approval is blocked.
- ✅ Classification comment is still posted (so reviewer can see the analysis).
- ❌ Auto-merge is still attempted (`gh pr merge --auto --squash`) — but **will hang** waiting for required approvals that never come.

## 🛠️ Recommended Solutions (in priority order)

### Option A: Bot Account Strategy (RECOMMENDED for production)

Create a dedicated GitHub App or Bot account for SupremeAI:

| Actor | Purpose | Token Source |
|---|---|---|
| `SaifulHaqueNiloy` (human) | Maintainer approvals, manual reviews | Personal PAT |
| `supremeai-bot` (GitHub App) | SupremeAI's PR submissions + commits | App installation token |
| `github-actions[bot]` | PR Helper auto-approval (works because bot ≠ author) | `github.token` (already used) |

**Implementation:**
1. Create GitHub App `supremeai-bot` with `contents:write` + `pull-requests:write` scopes
2. App's commits/PRs are authored by `supremeai-bot[bot]`
3. PR Helper uses `github.token` (runs as `github-actions[bot]`) → can approve `supremeai-bot`'s PRs ✅
4. Branch protection: require approval from `SaifulHaqueNiloy` OR `supremeai-bot`

### Option B: Mandatory Human Review (current de-facto policy)

**Current state** — no code change needed. Document this clearly:
- SupremeAI's PRs require manual `SaifulHaqueNiloy` approval
- PR Helper posts classification comment + enables auto-merge (waits for human approval)
- Maintainer reviews + approves → PR auto-merges

**Pros:** Zero infra change, safe, auditable
**Cons:** Slower (human-in-the-loop latency)

### Option C: Conditional Auto-Merge Skip

Modify Step 5 to detect author == token owner and skip auto-merge entirely (not just notice):

```yaml
- name: Enable auto-merge (squash) — skip for own PRs
  if: github.event.pull_request.head.user.login != github.repository_owner
  run: |
    gh pr merge "$PR" --auto --squash \
      && echo "auto-merge enabled" \
      || echo "::notice::..."
```

This avoids the "auto-merge waiting forever" anti-pattern.

## ✅ Decision (2026-09-20)

**Adopted:** Option B (Mandatory Human Review) as current policy.

**Roadmap:** Option A (Bot Account) for production-grade autonomy — tracked as separate issue.

## 🔗 Related

- `docs/security/SECURITY_GUARDIAN.md` — SG-03 (Explicit Auth), SG-11 (Bootstrap Trust)
- `.github/workflows/pr-helper.yml` — Step 5 approve + auto-merge steps
- `docs/master_docs/ARCH-GAP-01-DECISION-GAP-ANALYSIS.md` — GAP-02 full analysis

---

*GAP-02 fix — Self-Approval Policy · September 2026*
