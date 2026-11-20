"""Tests for architecture_gap_guardian."""
from pathlib import Path
import json
import pytest

from scripts.ci.architecture_gap_guardian import (
    audit_system_wiring,
    build_gap_report,
    generate_single_mermaid,
    SUBSYSTEMS,
)


def test_audit_wiring_detects_live_gateway_and_public():
    incoming, outgoing = audit_system_wiring()
    assert "Gateway_Entry" in incoming["Public_Studio_Web"] or "Public_Studio_Web" in outgoing
    assert "Gateway_Arbiter" in outgoing["Gateway_Entry"]
    assert "Browser_Relay" in outgoing["Gateway_Arbiter"]


def test_gap_report_flags_unlinked_modules():
    incoming, outgoing = audit_system_wiring()
    status_map, recommendations = build_gap_report(incoming, outgoing)

    # Live services should be marked LIVE
    assert status_map["Gateway_Entry"] == "LIVE"
    assert status_map["Browser_Relay"] == "LIVE"

    # Floating components must be explicitly flagged as GAPs, never falsely marked live
    assert status_map["Autonomous_Browser"] != "LIVE"
    assert status_map["RAG_Pipeline"] != "LIVE"
    assert len(recommendations) > 0


def test_generate_single_mermaid_has_live_and_gap_sections():
    incoming, outgoing = audit_system_wiring()
    status_map, recommendations = build_gap_report(incoming, outgoing)
    mmd = generate_single_mermaid(status_map, incoming, outgoing)

    assert "flowchart TD" in mmd
    assert "subgraph LiveMesh" in mmd
    assert "subgraph DetectedGaps" in mmd
    assert "classDef live" in mmd
    assert "classDef gap" in mmd
