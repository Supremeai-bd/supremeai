"""Migrate GEMINI/GROQ/OPENROUTER base-key reads to resolve_numbered_key."""
import os
import re

FAMILIES = ["GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
IMPORT_LINE = "from core.utils.api_key_resolver import resolve_numbered_key"


def migrate_file(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    orig = src
    for fam in FAMILIES:
        # os.environ.get("FAM") -> resolve_numbered_key("FAM")
        src = re.sub(
            r'os\.environ\.get\("' + fam + r'"\)',
            'resolve_numbered_key("' + fam + '")',
            src,
        )
        # os.getenv("FAM") -> resolve_numbered_key("FAM")
        src = re.sub(
            r'os\.getenv\("' + fam + r'"\)',
            'resolve_numbered_key("' + fam + '")',
            src,
        )
        # os.environ.get("FAM", "") -> resolve_numbered_key("FAM")
        src = re.sub(
            r'os\.environ\.get\("' + fam + r'",\s*""\)',
            'resolve_numbered_key("' + fam + '")',
            src,
        )
        # os.getenv("FAM", "") -> resolve_numbered_key("FAM")
        src = re.sub(
            r'os\.getenv\("' + fam + r'",\s*""\)',
            'resolve_numbered_key("' + fam + '")',
            src,
        )
    # add import if changed and not already present
    if src != orig and IMPORT_LINE not in src:
        # insert after first import line
        lines = src.splitlines(keepends=True)
        # find a good insertion point: after the last 'from core.' or 'import' at top
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_idx = i + 1
            else:
                # stop at first non-import, non-blank, non-comment line
                if line.strip() and not line.strip().startswith("#"):
                    break
        lines.insert(insert_idx, IMPORT_LINE + "\n")
        src = "".join(lines)
    if src != orig:
        open(path, "w", encoding="utf-8").write(src)
        return True
    return False


def main():
    files = []
    for root in ["core", "gateway", "scripts"]:
        for dp, _, fs in os.walk(root):
            for fn in fs:
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
    changed = 0
    for f in files:
        if migrate_file(f):
            changed += 1
    print("files changed:", changed)


if __name__ == "__main__":
    main()
