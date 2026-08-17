# Known Issues & Technical Debt

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When updating known issues or tech debt:
> 1. Add new items to the top of the relevant section.
> 2. When fixing an issue, change `[ ]` to `[x]` but do not delete it immediately.
> 3. Keep descriptions actionable.

This file tracks non-critical bugs, warnings, and technical debt in the SupremeAI project.
Agents should refer to this list when looking for optimization opportunities or when fixing related components.

## Current Issues
- [x] React error #31 crash on Admin Dashboard login (Active Monitor E2E) — raw error object `{code,message,errors}` passed to global toast and rendered as React child. Fixed in `apiInterceptor.ts` + `useErrorHandler.ts` + `ToastProvider.tsx` + `ui/Toast.tsx` (string coercion).
- [ ] Example Issue: Describe the issue here.

## Technical Debt
- [ ] Example Tech Debt: E.g., refactor this component to use a newer library version.

---
*(Check items off `[x]` as they are resolved and add new ones at the top of their respective sections)*
