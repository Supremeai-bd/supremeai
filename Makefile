# SupremeAI — developer entry points (make help)
#
# Why a Makefile and NOT a root pyproject.toml:
#   * `pytest.ini` and `ruff.toml` are the single sources of config (creed:
#     "the same job always follows the same code path"). A root `pyproject.toml`
#     would be a *second* config surface for the same two tools.
#   * `scripts/ci/bump_candidate_probe.py` / `py_dep_cve_guard.py` treat any
#     tracked `pyproject.toml` as a dependency manifest and start asserting
#     Poetry/PEP-621 shape + lock coverage against it. We have per-package
#     `requirements.lock` files; a stub pyproject would create false drift.
#   * Nothing in CI does `pip install -e .` — the images copy requirements
#     locks (see `gateway/Dockerfile`). So there is nothing to package.
#
# Everything below is a thin wrapper over the canonical command, so
# `make <target>` and the raw command can never diverge.

# PY= selects the interpreter. Most targets need PyYAML; `make venv` builds one.
PY ?= python3
ARGS ?=

.DEFAULT_GOAL := help
.PHONY: help venv gates test test-all lint guards index doctor clean decision-catalog

help: ## Show the available targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

decision-catalog: ## Print the AI decision-record reasoning-pattern catalog
	$(PY) scripts/ci/decision_records.py --catalog

venv: ## Create .venv with the lock deps + dev tools (use: make gates PY=.venv/bin/python)
	@$(PY) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11, 5) else 1)' || { \
		echo "The locks pin packages that require Python >= 3.11.5 (found $$($(PY) -V 2>&1))."; \
		echo "Pick a newer interpreter, e.g. make venv PY=python3.12"; exit 1; }
	$(PY) -m venv .venv
	.venv/bin/python -m pip install -q --upgrade pip
	.venv/bin/python -m pip install -q -r core/requirements.lock -r gateway/requirements.lock
	.venv/bin/python -m pip install -q pyyaml ruff pytest pytest-asyncio pytest-mock
	@echo "ready: make gates PY=.venv/bin/python"

gates: ## Fast fail-closed gates (same set the local guard roster runs first)
	@$(PY) -c "import yaml" 2>/dev/null || { echo "PyYAML missing in '$(PY)' — run 'make venv' then 'make gates PY=.venv/bin/python', or: $(PY) -m pip install pyyaml"; exit 1; }
	$(PY) scripts/ci/generate_agents_md.py --check
	$(PY) scripts/ops/generate_script_index.py --check-committed
	$(PY) scripts/ci/validate_config_registry.py
	$(PY) scripts/ci/check_config_contract.py
	$(PY) scripts/ci/ghost_host_guard.py --self-test
	$(PY) scripts/ci/ghost_host_guard.py --check
	$(PY) scripts/ci/sarif_permission_guard.py --self-test
	$(PY) scripts/ci/sarif_permission_guard.py --check
	$(PY) scripts/ci/deploy_preflight_guard.py --step1-syntax

test: ## Run the PR battery (@config/ci/pr-battery.args)
	$(PY) -m pytest @"config/ci/pr-battery.args"

test-all: ## Run the full configured suite (tests/ core/tests/ gateway/tests/)
	$(PY) -m pytest

lint: ## ruff check (fatal subset, matches CI) (pass ARGS=<paths> to narrow)
	$(PY) -m ruff check --select E9,F63,F7,F82 $(if $(ARGS),$(ARGS),core/ gateway/ browser/)

lint-all: ## ruff check (all rules, advisory)
	$(PY) -m ruff check $(if $(ARGS),$(ARGS),core/ gateway/ browser/)

guards: ## Full guard roster (slower; the same list CI runs in Tier 1/2)
	$(PY) scripts/ci/run_all_guards.py

index: ## Regenerate scripts/ops/_INDEX.md after adding/removing a script
	$(PY) scripts/ops/generate_script_index.py

doctor: ## Deployment preflight doctor (reads the live fleet, no writes)
	$(PY) scripts/ci/deploy_doctor.py --help >/dev/null 2>&1 && $(PY) scripts/ci/deploy_doctor.py || \
		echo "deploy_doctor has no default mode; see 'python scripts/ci/deploy_doctor.py --help'"

clean: ## Remove local caches (does not touch the git tree)
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__
	find . -name '__pycache__' -type d -prune -not -path './.git/*' -exec rm -rf {} + 2>/dev/null || true

promote-decision:
	python scripts/ci/promote_decision_record.py --help
