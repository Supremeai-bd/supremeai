#!/usr/bin/env python3
"""
Deterministic Firebase Configuration Generator.

Reads `firebase.template.json` and deterministically substitutes the backend URLs.
Zero-hardcode policy — fails fast (exit 1) if any of the following hold:
  - the template file is missing
  - BACKEND_URL (or equivalents) is not configured in the environment
  - unresolved `{{...}}` placeholders remain after substitution
  - the substituted output is not valid JSON
  - any required rewrite (`/api/**`, `/api/v1/**`, `/admin-api/**`) is missing
    from a hosting site (this used to be a WARNING — it is now fail-closed,
    because a silently-missing API rewrite breaks the deployed SPA backend)
  - a rewrite destination points at a foreign origin (not the canonical
    backend origin derived from BACKEND_URL)
  - a rewrite destination breaks source-prefix proof (e.g. `/api/**` routed
    to `{origin}/admin-api/...`)
  - the SPA fallback rewrite (`**` -> `/index.html`) is missing
"""

import json
import os
import re
import sys
from urllib.parse import urlsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Rewrite sources every hosting site MUST expose (order-insensitive).
REQUIRED_REWRITE_SOURCES: tuple[str, ...] = ("/api/**", "/api/v1/**", "/admin-api/**")
SPA_FALLBACK_SOURCE = "**"
SPA_FALLBACK_DESTINATION = "/index.html"


def _origin_of(url: str) -> str:
    """Return lowercase scheme://host[:port] for an absolute URL, else ''."""
    parts = urlsplit(str(url))
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def _validate_hosting(hosting: list[dict], backend_origin: str) -> list[str]:
    """Return a list of human-readable errors (empty list == valid)."""
    errors: list[str] = []
    for site in hosting:
        target = site.get("target", "default")
        rewrites = site.get("rewrites", [])
        if not isinstance(rewrites, list):
            errors.append(f"[{target}] 'rewrites' is not a list")
            continue

        by_source: dict[str, dict] = {}
        for rw in rewrites:
            src = rw.get("source")
            if src and src not in by_source:
                by_source[src] = rw

        for required in REQUIRED_REWRITE_SOURCES:
            rw = by_source.get(required)
            if rw is None:
                errors.append(
                    f"[{target}] missing required rewrite {required} "
                    f"(a silently-missing API rewrite breaks the deployed SPA backend)"
                )
                continue
            dest = str(rw.get("destination", ""))
            dest_origin = _origin_of(dest)
            if not dest_origin:
                errors.append(
                    f"[{target}] rewrite {required} destination is not an absolute "
                    f"URL: {dest!r}"
                )
                continue
            if dest_origin != backend_origin:
                errors.append(
                    f"[{target}] rewrite {required} destination origin "
                    f"{dest_origin} does not match canonical backend origin "
                    f"{backend_origin} (foreign destination rejected)"
                )
                continue
            # Prefix-proof: /api/** must route into {origin}/api/...,
            # /admin-api/** into {origin}/admin-api/..., etc.
            required_prefix = required[:-3]  # strip trailing "/**"
            dest_path = urlsplit(dest).path
            if not dest_path.startswith(required_prefix.rstrip("/") + "/"):
                errors.append(
                    f"[{target}] rewrite {required} destination path {dest_path!r} "
                    f"does not route into {required_prefix!r} (source-prefix proof failed)"
                )

        spa = by_source.get(SPA_FALLBACK_SOURCE)
        if spa is None:
            errors.append(
                f"[{target}] missing SPA fallback rewrite {SPA_FALLBACK_SOURCE!r} "
                f"-> {SPA_FALLBACK_DESTINATION!r}"
            )
        elif str(spa.get("destination", "")) != SPA_FALLBACK_DESTINATION:
            errors.append(
                f"[{target}] SPA fallback destination "
                f"{spa.get('destination')!r} != {SPA_FALLBACK_DESTINATION!r}"
            )
    return errors


def generate_firebase_config() -> None:
    template_path = "firebase.template.json"
    output_path = "firebase.json"

    print("=== Generating Firebase Configuration ===")

    if not os.path.exists(template_path):
        print(f"❌ ERROR: Template file {template_path} not found.")
        sys.exit(1)

    backend_url = (
        os.getenv("BACKEND_URL")
        or os.getenv("VITE_BACKEND_URL")
        or os.getenv("VITE_API_URL")
        or os.getenv("USER_BACKEND_URL")
        or os.getenv("VITE_USER_BACKEND")
    )

    if not backend_url:
        print(
            "❌ ERROR: BACKEND_URL (or VITE_BACKEND_URL / VITE_API_URL) must be set "
            "in the environment."
        )
        sys.exit(1)

    backend_origin = _origin_of(backend_url)
    if not backend_origin:
        print(
            f"❌ ERROR: BACKEND_URL is not an absolute URL with scheme and host: "
            f"{backend_url!r}"
        )
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        config_text = f.read()

    # Unify all placeholders to the single backend URL
    config_text = config_text.replace("{{BACKEND_URL}}", backend_url)
    config_text = config_text.replace("{{USER_BACKEND_URL}}", backend_url)
    config_text = config_text.replace("{{ADMIN_BACKEND_URL}}", backend_url)

    # Placeholder detection must match the *pattern* {{NAME}}, not a bare "}}"
    # substring: any JSON doc ending in two closing braces (e.g. {"hosting":
    # {...}}) contains "}}" legitimately. The old substring check was a latent
    # false-positive waiting for such a template shape.
    unresolved = re.search(r"\{\{[^{}]*\}\}", config_text)
    if unresolved:
        print(
            f"❌ ERROR: Unresolved placeholder {unresolved.group(0)!r} remains in "
            f"the generated firebase.json."
        )
        sys.exit(1)

    try:
        config_json = json.loads(config_text)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Generated firebase.json is not valid JSON. {e}")
        sys.exit(1)

    # Verify rewrite semantics — fail closed (was WARNING-only before zero-hardcode)
    hosting = config_json.get("hosting", [])
    if isinstance(hosting, dict):
        hosting = [hosting]

    errors = _validate_hosting(hosting, backend_origin)
    if errors:
        print("❌ ERROR: firebase.json hosting rewrite contract violated:")
        for err in errors:
            print(f"   - {err}")
        print(
            "   Fix firebase.template.json (or BACKEND_URL) so every hosting site "
            "rewrites /api/**, /api/v1/** and /admin-api/** to the canonical "
            "backend origin and keeps the SPA fallback."
        )
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config_json, f, indent=2)

    print(f"✅ Successfully generated {output_path}")
    print(f"   Backend URL: {backend_url}")
    print(
        f"   Rewrite contract: {len(REQUIRED_REWRITE_SOURCES)} required API "
        f"rewrites + SPA fallback validated on {len(hosting)} site(s)"
    )


if __name__ == "__main__":
    generate_firebase_config()
