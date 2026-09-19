# PostgreSQL init scripts

This directory is bind-mounted into the `postgres` service of
`docker-compose.production.yml`:

```yaml
volumes:
  - ./init-scripts:/docker-entrypoint-initdb.d
```

The official `postgres` image runs every `*.sql`, `*.sql.gz` and `*.sh`
file in `/docker-entrypoint-initdb.d` in alphabetical order — but **only
the first time the data directory is initialised** (i.e. when
`postgres_data` is empty).

Why this directory is tracked in git: if it did not exist, `docker
compose up` would auto-create an untracked, root-owned `init-scripts/`
on the host (R-01, issue #535). Keeping a placeholder here makes the
mount resolve deterministically.

## Adding an init script

- Name files with an explicit order prefix: `001-<name>.sql`,
  `002-<name>.sh`, ...
- Keep scripts idempotent where possible (`CREATE EXTENSION IF NOT EXISTS ...`).
- The pgvector extension is required by the schema — the image
  (`pgvector/pgvector:pg16`) already ships it; the usual first statement is:
  `CREATE EXTENSION IF NOT EXISTS vector;`
- Scripts run as the superuser defined by `POSTGRES_USER`; do not embed
  secrets — use env vars from `.env.production`.
