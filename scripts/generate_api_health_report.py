# ruff: noqa: T201, BLE001, E501, PLW1508, SIM105
import json
import sys
from pathlib import Path

from fastapi.routing import APIRoute


def generate_health_report():
    # Adjust python path to allow importing from backend
    backend_path = Path(__file__).resolve().parent.parent / "backend"
    sys.path.insert(0, str(backend_path))

    # Import the FastAPI app
    from core.app import app

    report_path = backend_path / "pytest-report.json"

    tests = {"tests": []}
    if report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            try:
                tests = json.load(f)
            except json.JSONDecodeError:
                pass

    report = "### 🩺 API Health & Route Coverage Matrix\n\n"
    report += "| Endpoint Path | Method | Has Test? | Status |\n|---|---|---|---|\n"

    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            methods = ", ".join(list(route.methods - {"HEAD"}))
            # Simple logic to check if route path is mentioned in tests
            has_test = any(path.strip('/').replace('/', '_') in test.get('nodeid', '') for test in tests.get('tests', []))
            if not has_test:
                # Also check by direct string match in nodeid just in case
                has_test = any(path in test.get('nodeid', '') for test in tests.get('tests', []))

            status_icon = "✅" if has_test else "⚠️"
            status_text = "Pass" if has_test else "Untested"
            report += f"| `{path}` | `{methods}` | {status_icon} | {status_text} |\n"

    try:
        print(report)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(report.encode("utf-8"))

if __name__ == "__main__":
    generate_health_report()
