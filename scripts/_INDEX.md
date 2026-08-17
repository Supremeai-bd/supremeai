# scripts/ — File Index
> AI: পুরো ফোল্ডার স্ক্যান না করে এই index পড়ুন।

## Context Mesh (Phase B & C) — নতুন
| File | কী করে | কখন ব্যবহার |
|---|---|---|
| `checkpoint_update.py` | CHECKPOINT.md অটো-আপডেট | সেশন শেষে |
| `context_snapshot.py` | Task-specific context তৈরি | কাজ শুরুর আগে |
| `ai/memory_write.py` | Supabase-এ session memory save | সেশন শেষে |
| `ai/memory_read.py` | Past memory semantic search | কাজ শুরুর আগে |

## Environment & Secrets
| File | কী করে |
|---|---|
| `check_env_health.py` | সব env + service health check |
| `upload_to_infisical.py` | Local .env → Infisical vault sync |
| `push_all_render_envs.py` | Infisical → Render env vars sync |
| `sync_all_platforms_env.py` | সব platform-এ env sync |
| `verify_infisical_env.py` | Infisical secrets verify |
| `audit_env_usage.py` | কোন env var কোথায় ব্যবহার হচ্ছে |

## Deployment & CI
| File | কী করে |
|---|---|
| `check_deploys.py` | Render deployment status |
| `fetch_render_failure_logs.py` | Render deploy failure logs |
| `analyze_github_failures.py` | GitHub Actions failure analysis |
| `fix_github_actions_failures.py` | GitHub Actions auto-fix |
| `cancel_hanging_deploys.py` | Stuck deploy বাতিল করা |
| `render_build_backend.sh` | Render backend build script |

## Database & Migrations
| File | কী করে |
|---|---|
| `db/` | DB migration scripts |
| `migrate.py` | Run Alembic migrations |
| `bootstrap_sentinel_tables.py` | Sentinel table setup |

## Analysis & Quality
| File | কী করে |
|---|---|
| `find_dead_code.py` | Unused code detection |
| `find_duplicates.py` | Duplicate code finder |
| `find_secrets.py` | Accidental secret detection |
| `generate_types.py` | Auto-generate TypeScript types from backend |
| `safety_guard.py` | Security scan |

## AI & Knowledge
| File | কী করে |
|---|---|
| `ai/` | AI-specific scripts (memory, model, bias detection) |
| `knowledge_indexer.py` | ChromaDB codebase indexer |
| `supreme_context_builder.py` | Full codebase XML context generator |
| `generate_smart_docs.py` | Auto-generate documentation |
