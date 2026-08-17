import os
import sys

import pytest


# Ensure repository root and scripts are importable
repo_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
scripts_dir = os.path.join(repo_root, "scripts")
paths = [".", repo_root, scripts_dir]
for p in paths:
    if p and p not in sys.path:
        sys.path.insert(0, p)

# Disable pytest-cov plugin
args = [
    "-p",
    "no:pytest_cov",
    "backend/tests/test_gcp_integration.py::test_gcp_firestore_integration_queue",
    "backend/tests/test_gcp_integration.py::test_gcp_pubsub_publish_pull",
    "backend/tests/test_gcp_integration.py::test_gcp_cloud_run_router_route",
    "-q",
]

ret = pytest.main(args)
print("pytest exit code:", ret)  # noqa: T201
sys.exit(ret)
