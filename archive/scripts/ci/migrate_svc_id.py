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
    for svc, service in MAPPING.items():
        text = re.sub(
            r'os\.environ\.get\("' + svc + r'"\)',
            'os.environ.get("' + service + '", os.environ.get("' + svc + '", ""))',
            text,
        )
        text = re.sub(
            r'os\.environ\.get\("' + svc + r'",\s*""\)',
            'os.environ.get("' + service + '", os.environ.get("' + svc + '", ""))',
            text,
        )
        text = re.sub(
            r'os\.getenv\("' + svc + r'"\)',
            'os.getenv("' + service + '", os.getenv("' + svc + '", ""))',
            text,
        )
        text = re.sub(
            r'os\.getenv\("' + svc + r'",\s*""\)',
            'os.getenv("' + service + '", os.getenv("' + svc + '", ""))',
            text,
        )
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
