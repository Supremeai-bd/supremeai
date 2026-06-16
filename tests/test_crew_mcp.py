import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.mcp_client import MCPClient
from brain.crewai_agents import CrewAgent, CrewTask, SupremeCrew

def test_mcp_client_tool_listing():
    client = MCPClient("mock_server", ["mock_cmd"])
    client.process = MagicMock()
    
    # Mock stdout to return a valid jsonrpc response
    mock_response = '{"jsonrpc": "2.0", "result": {"tools": [{"name": "web_scrape", "description": "Scrape website content"}]}, "id": 1}\n'
    client.process.stdout.readline.return_value = mock_response
    
    tools = client.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "web_scrape"

def test_crew_agent_and_sequential_crew():
    # Mock model router
    mock_router = MagicMock()
    mock_router.route_and_generate.side_effect = [
        {"text": "Research data: python has 3.12 version"},
        {"text": "Refined summary of python version details"}
    ]
    
    researcher = CrewAgent(
        role="Researcher",
        goal="Gather tech facts",
        backstory="Curious expert",
        model_router=mock_router
    )
    writer = CrewAgent(
        role="Writer",
        goal="Draft content",
        backstory="Creative copywriter",
        model_router=mock_router
    )
    
    task1 = CrewTask("Find Python latest version details", researcher)
    task2 = CrewTask("Summarize research findings into a post", writer)
    
    crew = SupremeCrew(agents=[researcher, writer], tasks=[task1, task2])
    result = crew.kickoff()
    
    assert "Research data:" in result
    assert "Refined summary" in result
    assert mock_router.route_and_generate.call_count == 2
