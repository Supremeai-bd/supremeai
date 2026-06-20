import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from tools.vision_agent import VisionAgent

def test_vision_agent_image_no_easyocr():
    with patch.dict("sys.modules", {"easyocr": None}):
        agent = VisionAgent()
        # Disabling module import temporarily to test import error pathway
        with patch("builtins.__import__", side_effect=ImportError("easyocr not found")):
            res = agent.analyze_image("dummy_image.png")
            assert not res["success"]
            assert "easyocr" in res["error"].lower()

def test_vision_agent_image_success():
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([0, 0, 10, 10], "Hello World", 0.95),
        ([0, 10, 10, 20], "Test", 0.85)
    ]
    
    mock_easyocr = MagicMock()
    mock_easyocr.Reader.return_value = mock_reader
    with patch.dict("sys.modules", {"easyocr": mock_easyocr}):
        agent = VisionAgent()
        res = agent.analyze_image("dummy_image.png")
        assert res["success"]
        assert "Hello World\nTest" == res["text"]
        assert res["structured"]["line_count"] == 2
        assert res["structured"]["average_confidence"] == 0.9000

def test_vision_agent_pdf_extraction():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        
        # Test PDF plumber mock fallback
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page Content"
        mock_pdf.pages = [mock_page]
        
        mock_plumber = MagicMock()
        mock_plumber.open.return_value = MagicMock(__enter__=MagicMock(return_value=mock_pdf))
        
        with patch.dict("sys.modules", {"pdfplumber": mock_plumber, "fitz": None}):
            
            agent = VisionAgent()
            res = agent.analyze_pdf(pdf_path)
            assert res["success"]
            assert res["pages"] == 1
            assert "Page Content" in res["text"]

def test_vision_agent_chart_hints():
    mock_reader = MagicMock()
    mock_reader.readtext.return_value = [
        ([0, 0, 10, 10], "X: label", 0.95),
        ([0, 10, 10, 20], "Data Value", 0.85)
    ]
    
    mock_easyocr = MagicMock()
    mock_easyocr.Reader.return_value = mock_reader
    with patch.dict("sys.modules", {"easyocr": mock_easyocr}):
        agent = VisionAgent()
        res = agent.analyze_chart("chart.png")
        assert res["success"]
        assert "X: label" in res["structured"]["chart_hints"]
        assert res["structured"]["estimated_labels"] == 2
