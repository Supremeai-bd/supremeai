# tests/tools/test_meta_architect_coverage_full.py
"""Comprehensive unit tests for backend/tools/meta_architect.py targeting 80%+ line coverage."""

import tempfile
from pathlib import Path

import pytest

from tools.meta_architect import MetaArchitect


@pytest.mark.asyncio
async def test_meta_architect_analyze_codebase_empty_dir():
    architect = MetaArchitect()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await architect.analyze_codebase(root_dir=tmpdir)
        assert result["metrics"]["total_files"] == 0
        assert result["metrics"]["total_lines"] == 0


@pytest.mark.asyncio
async def test_meta_architect_analyze_codebase_with_files_and_strategic_docs():
    architect = MetaArchitect()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample python file
        py_file = Path(tmpdir) / "sample.py"
        py_file.write_text("print('hello world')\n", encoding="utf-8")

        # Create a strategic doc mentioning 'gap'
        doc_file = Path(tmpdir) / "GAP_REPORT.md"
        doc_file.write_text("Found a security gap in module.", encoding="utf-8")

        result = await architect.analyze_codebase(root_dir=tmpdir, strategic_docs=[str(doc_file)])

        assert result["metrics"]["total_files"] >= 1
        assert "py" in result["metrics"]["languages"]
        assert len(result["strategic_gaps_context"]) >= 1


@pytest.mark.asyncio
async def test_meta_architect_analyze_codebase_nonexistent_doc():
    architect = MetaArchitect()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await architect.analyze_codebase(
            root_dir=tmpdir, strategic_docs=["/nonexistent/doc.md"]
        )
        assert result["metrics"]["total_files"] == 0
