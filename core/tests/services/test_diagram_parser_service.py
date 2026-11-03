"""
Tests for services/diagram_parser_service.py
Pure-parsing tests; network/LLM paths are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram_parser_service import (
    DiagramParserService,
    DiagramType,
    DrawIOParser,
    MermaidParser,
    PlantUMLParser,
)

# ── MermaidParser ─────────────────────────────────────────────────────────────


def test_mermaid_parser_nodes_and_edges():
    # Edge regex requires no space between source and arrow.
    content = "graph TD\nA[Frontend]\nB[Backend]\nC[Database]\nA-->B\nB-->C\n"
    nodes, edges = MermaidParser.parse(content)

    assert {n.id for n in nodes} == {"A", "B", "C"}
    assert {e.source for e in edges} == {"A", "B"}
    assert edges[0].source == "A"
    assert edges[0].target == "B"
    assert edges[0].edge_type == "directed"


def test_mermaid_parser_undirected_edge():
    content = "graph LR\nA---B\n"
    _, edges = MermaidParser.parse(content)
    assert edges[0].edge_type == "undirected"


def test_mermaid_parser_dashed_arrow():
    content = "graph TD\nA==>B\n"
    _, edges = MermaidParser.parse(content)
    assert edges[0].edge_type == "dashed_directed"


def test_mermaid_parser_subgraph_grouping():
    content = "graph TD\n    subgraph Auth\n        A[Login] --> B[Validate]\n    end\n"
    nodes, _ = MermaidParser.parse(content)
    assert any(n.id == "A" for n in nodes)
    assert any(n.id == "B" for n in nodes)


# ── PlantUMLParser ────────────────────────────────────────────────────────────


def test_plantuml_parser_components():
    content = "@startuml\n[Frontend] description\n[Backend] description\n[Frontend] --> [Backend]\n@enduml\n"
    nodes, edges = PlantUMLParser.parse(content)
    assert len(nodes) >= 1
    assert any(n.component_type == "component" for n in nodes)
    assert len(edges) >= 1
    assert edges[0].edge_type == "association"


# ── DrawIOParser ──────────────────────────────────────────────────────────────


def test_drawio_parser_xml():
    xml = (
        "<mxfile><mxGraphModel>"
        '<mxCell id="1" value="Server" style="ellipse" vertex="1"/>'
        '<mxCell id="2" value="DB" style="shape=process" vertex="1"/>'
        '<mxCell id="3" source="1" target="2" edge="1"/>'
        "</mxGraphModel></mxfile>"
    )
    nodes, edges = DrawIOParser.parse(xml)

    assert any(n.component_type == "terminal" for n in nodes)
    assert any(n.component_type == "process" for n in nodes)
    assert len(edges) == 1
    assert edges[0].edge_type == "directed"


def test_drawio_parser_dashed_edge():
    xml = (
        "<mxfile><mxGraphModel>"
        '<mxCell id="1" value="A" style="dashed" source="1" target="2" edge="1"/>'
        "</mxGraphModel></mxfile>"
    )
    _, edges = DrawIOParser.parse(xml)
    assert edges[0].edge_type == "dashed"


# ── DiagramParserService.detect_format ────────────────────────────────────────


def test_detect_format_mermaid_by_content():
    svc = DiagramParserService()
    assert svc.detect_format("graph TD\n A-->B") == DiagramType.MERMAID


def test_detect_format_plantuml_by_content():
    svc = DiagramParserService()
    assert svc.detect_format("@startuml\nA -> B\n@enduml") == DiagramType.PLANTUML


def test_detect_format_drawio_by_content():
    svc = DiagramParserService()
    assert svc.detect_format("<?xml version='1.0'?><mxfile>") == DiagramType.DRAWIO


def test_detect_format_fallback_to_image():
    svc = DiagramParserService()
    assert svc.detect_format("random text with no diagram markers") == DiagramType.IMAGE


# ── DiagramParserService.parse (text paths) ───────────────────────────────────


@pytest.mark.anyio
async def test_parse_mermaid_returns_nodes_edges():
    svc = DiagramParserService()
    nodes, edges = await svc.parse(
        content="graph TD\nA[Login]\nB[Validate]\nA-->B\n", filename="d.mmd"
    )
    assert len(nodes) >= 1
    assert any(e.source == "A" and e.target == "B" for e in edges)


@pytest.mark.anyio
async def test_parse_plantuml_by_filename():
    svc = DiagramParserService()
    nodes, edges = await svc.parse(content="[A] -> [B]", filename="arch.puml")
    assert isinstance(nodes, list)
    assert isinstance(edges, list)


@pytest.mark.anyio
async def test_parse_drawio_by_filename():
    svc = DiagramParserService()
    nodes, edges = await svc.parse(
        content=None,
        filename="model.drawio",
        image_path=None,
    )
    # Without XML content and no image_path, returns empty
    assert nodes == [] and edges == []


# ── DiagramParserService.to_infrastructure (mocked LLM) ───────────────────────


@pytest.mark.anyio
async def test_to_infrastructure_success():
    svc = DiagramParserService()
    nodes = [
        MagicMock(label="Frontend"),
        MagicMock(label="Backend"),
    ]
    edges = []
    with patch("services.diagram_parser_service.ModelRouter") as mock_router_cls:
        mock_router = AsyncMock()
        mock_router_cls.return_value = mock_router
        # Phase-2.1 (#2249): facade dict contract key is "text"
        mock_router.async_route_and_generate.return_value = {
            "success": True,
            "text": 'resource "aws_instance" "web" {}',
        }

        result = await svc.to_infrastructure(nodes, edges, provider="aws", iac_tool="terraform")
        assert result["status"] == "success"
        assert "terraform" in result["iac_tool"]
        assert "aws" in result["provider"]


@pytest.mark.anyio
async def test_to_infrastructure_failure_returns_error():
    svc = DiagramParserService()
    with patch("services.diagram_parser_service.ModelRouter") as mock_router_cls:
        mock_router = AsyncMock()
        mock_router_cls.return_value = mock_router
        mock_router.async_route_and_generate.side_effect = RuntimeError("LLM down")

        result = await svc.to_infrastructure([], [])
        assert result["status"] == "error"
        assert "LLM down" in result["error"]


# ── Singleton ─────────────────────────────────────────────────────────────────


def test_get_diagram_parser_returns_same_instance():
    from services import diagram_parser_service
    from services.diagram_parser_service import get_diagram_parser

    diagram_parser_service._service_instance = None  # reset
    a = get_diagram_parser()
    b = get_diagram_parser()
    assert a is b
