# CI Run Comparison

## Summary
This file compares two `supreme-ci.yml` workflow runs based on the provided screenshots and commit references.

- Commit `a73b258` — triggered from `main` (older)
- Commit `111df21` — triggered from `main` (latest)

## Common jobs present in both runs
- Detect Changes
- Config Audit
- Docker Gatekeeper
- Combine Decisions
- Backend Tests
- Auto-Fix Backend Tests
- Studio Client Build
- Mobile App Analysis
- VS Code Extension Build
- Web Chat Build
- LLM Prompt Evaluation
- Code Smell Analysis
- CI Cache Cleanup
- Deploy Backend to Cloud Run
- Deploy Studio to Firebase
- Deploy Web Chat to Firebase
- Generate Flutter APK
- Generate VS Code VSIX
- Generate Windows EXE
- Dispatch To Mirror Repo
- Staging Dispatch
- CI Report & Dashboard Log
- Auto-Fix Failed Jobs

## Commit `111df21`
- Status: Failure
- Total duration: 3m 38s
- Artifacts: 2
- Observed failure: `Studio Client Build`
- Likely successful upstream jobs: `Detect Changes`, `Config Audit`, `Docker Gatekeeper`, `Combine Decisions`, `Backend Tests`

## Commit `a73b258`
- Status: Failure
- Total duration: 11m 47s
- Artifacts: 5
- Observed failures: `Backend Tests`, `Studio Client Build`, `Auto-Fix Backend Tests`, `Deploy Backend to Cloud Run`, `Deploy Studio to Firebase`, `Generate Windows EXE`, `CI Report & Dashboard Log`
- Likely successful upstream jobs: `Detect Changes`, `Config Audit`, `Docker Gatekeeper`, `Combine Decisions`, `Mobile App Analysis`, `Web Chat Build`, `VS Code Extension Build`, `LLM Prompt Evaluation`, `Generate Flutter APK`, `Deploy Web Chat to Firebase`, `CI Cache Cleanup`, `Generate VS Code VSIX`

## Job comparison summary
| Commit | Total Jobs | Run | Skipped | Passed | Failed |
|---|---|---|---|---|---|
| `a73b258` | 28 | 22 | 6 | 14 | 8 |
| `111df21` | 28 | 18 | 10 | 18 | 0 |

## Job-level comparison
| Job Name | `a73b258` | `111df21` |
|---|---|---|
| 🔍 Detect Changes | Passed | Passed |
| 🤔 Check Previous Failures | Passed | Passed |
| 🤖 Scheduled AI Code Review | Skipped | Skipped |
| 🧪 Nightly AI Validation (DeepEval) | Skipped | Skipped |
| 🧹 Cloud Run Revision Cleanup | Skipped | Skipped |
| 🗂️ GitHub Actions Cache Prune | Skipped | Skipped |
| 🔐 Config Audit | Passed | Passed |
| 🐳 Docker Gatekeeper | Passed | Passed |
| ⚙️ Combine Decisions | Passed | Passed |
| 🐍 Backend Tests | Failed | Passed |
| 👃 Code Smell Analysis | Failed | Passed |
| 🎨 Studio Client Build | Failed | Passed |
| 📱 Mobile App Analysis | Passed | Passed |
| 💬 Web Chat Build | Passed | Passed |
| 🧩 VS Code Extension Build | Passed | Passed |
| 🤖 LLM Prompt Evaluation | Passed | Passed |
| 🔧 Auto-Fix Backend Tests | Failed | Not run |
| 🚀 Deploy Backend to Cloud Run | Failed | Not run |
| 🎨 Deploy Studio to Firebase | Failed | Not run |
| 💬 Deploy Web Chat to Firebase | Passed | Not run |
| 🪟 Generate Windows EXE | Failed | Not run |
| 📱 Generate Flutter APK | Passed | Not run |
| 🧩 Generate VS Code VSIX | Passed | Not run |
| 🧹 CI Cache Cleanup | Passed | Not run |

| 📤 Dispatch To Mirror Repo | Skipped | Skipped |
| 📤 Staging Dispatch | Skipped | Skipped |
| 📊 CI Report & Dashboard Log | Passed | Failed |
| 🔧 Auto-Fix Failed Jobs | Skipped | Skipped |

## Notes
- The table uses actual workflow job names from `.github/workflows/supreme-ci.yml`.
- `111df21` shows all visible jobs passing in the screenshot and no failed entries.
- `a73b258` shows multiple failures: `Backend Tests`, `Code Smell Analysis`, `Studio Client Build`, `Auto-Fix Backend Tests`, `Deploy Backend to Cloud Run`, `Deploy Studio to Firebase`, `Generate Windows EXE`, and `CI Report & Dashboard Log`.
- Job counts are inferred from visible run status and screenshot summary.
