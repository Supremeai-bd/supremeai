"""Migrate Python scripts to read RENDER_*_SERVICE_ID with fallback to *_SVC_ID."""
import os
import re

MAPPING = {
    "RENDER_API_SVC_ID": "RENDER_API_SERVICE_ID",
    "RENDER_BRAIN_SVC_ID": "RENDER_BRAIN_SERVICE_ID",
    "RENDER_CI_RUNNER_SVC_ID": "RENDER_CI_RUNNER_SERVICE_ID",
    "RENDER_MCP_SVC_ID": "RENDER_MCP_SERVICE_ID",
    "RENDER_PRIMARY_SVC_ID": "RENDER_CORE_SERVICE_ID",
    "RENDER_SCRAPER_SVC_ID": "RENDER_SCRAPER_SERVICE_ID",
    "RENDER_WORKER_SVC_ID": "RENDER_WORKER_SERVICE_ID",
}


def migrate(text):
    """Rewrite `<getter>("SVC_ID")` reads to `<getter>("SERVICE_ID", <getter>("SVC_ID", ""))`.

    Two properties matter and the original four-regex version had neither:

    * **no nesting** — the plain shape (`get("SVC")`, no default) was rewritten
      first, and the with-default pattern then matched the *inner* call the
      rewrite had just produced, yielding
      `get("NEW", get("NEW", get("SVC", "")))`. The shapes are now applied
      longest-first inside a single pass over a placeholder, so a produced
      fallback is never re-matched.
    * **idempotent** — an already-migrated call is detected and left alone, so
      re-running the migration (or running it over an already-migrated file)
      cannot double-wrap and change behaviour.
    """
    for svc, service in MAPPING.items():
        for getter in ("os.environ.get", "os.getenv"):
            migrated = f'{getter}("{service}", {getter}("{svc}", ""))'
            token = f"\x00migrate-svc:{service}:{getter}\x00"
            text = text.replace(migrated, token)
            text = re.sub(re.escape(getter) + r'\("' + svc + r'",\s*""\)', migrated, text)
            text = re.sub(re.escape(getter) + r'\("' + svc + r'"\)', migrated, text)
            text = text.replace(token, migrated)
    return text


def main():
    files = []
    for root in ["core", "gateway", "scripts", ".github"]:
        for dp, _, fs in os.walk(root):
            for fn in fs:
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
    changed = 0
    for f in files:
        src = open(f, encoding="utf-8", errors="replace").read()
        new = migrate(src)
        if new != src:
            open(f, "w", encoding="utf-8").write(new)
            changed += 1
    print("files changed:", changed)


if __name__ == "__main__":
    main()
