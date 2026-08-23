# Coding Conventions & Guidelines

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding new conventions:
> 1. Place it in the appropriate category.
> 2. Keep the rule absolute, clear, and strict.
> 3. Ensure it aligns with the SupremeAI Zero-Cost and Scalability philosophy.

This document outlines the coding standards, folder structure rules, and naming conventions for the SupremeAI project.
Agents MUST strictly adhere to these conventions when generating or modifying code.

## 1. Naming Conventions
- **Variables/Functions:** camelCase (e.g., `getUserData`)
- **Classes/Interfaces:** PascalCase (e.g., `UserProfile`)
- **Constants:** UPPER_SNAKE_CASE (e.g., `MAX_RETRY_LIMIT`)
- **File Names:** kebab-case (e.g., `user-profile.ts`) unless framework specifically requires otherwise.

## 2. Directory Structure
- Follow the existing monorepo structure in `/apps` and `/packages`.
- Do not create arbitrary top-level folders.

## 3. General Rules
- Always use the most strict type checking possible (e.g., TypeScript `strict: true`).
- No hardcoded secrets (use `.env` and `Infisical`).
- Prioritize modular and DRY (Don't Repeat Yourself) code.
- **Intentional Mocks:** The project is production-ready, but some data or features are intentionally mocked. Do NOT attempt to "fix" or remove these mocks unless the user explicitly instructs you to do so.
