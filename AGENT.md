# 🔱 SupremeAI Agent Guidelines (এজেন্ট কাজের নিয়মাবলী)

This rule file applies to **ALL AI AGENTS** (.antigravity agent, .kilo agent, .gemini agent, etc.) working on this workspace. You MUST strictly follow these constitutional directives:

---

## 1️⃣ No Gaps (০% গ্যাপ পলিসি)
- **Zero Gap Allowed**: Never leave placeholders, mock codes, or incomplete implementations in the codebase.
- **Verification**: Every implemented feature must have working unit/integration tests, and all tests must pass before ending your turn.
- **Docker/Cloud Alignment**: Ensure development environment and production environment configurations (Dockerfile, docker-compose.yml, render.yaml, railway.json) are always fully synchronized and functional.

---

## 2️⃣ Manual Task Management (ম্যানুয়াল টাস্ক ট্র্যাকিং)
- **Checklist Maintenance**: Any tasks that cannot be automated must be listed in the manual tasks section of `SUPREMEAI_2.0_WORK_PLAN.md` and `account_skill_tools_setup.md`.
- **Status Updates**: As soon as a manual task is completed by the user or verified, update the checklist checkbox to completed (`[x]`).
- **Reminders**: Always schedule a recurring background reminder/timer (1-2 hours interval) via the `schedule` tool to prompt the user about outstanding manual tasks.

---

## 3️⃣ Language & Style (ভাষা ও লেখার ধরন)
- **Language**: You must explain your steps in Bengali (বাংলা) and keep explanations concise (shortly).
- **Git Push Restriction**: Do NOT push to GitHub repository (`git push`) unless explicitly requested by the user. Keep commits local.
