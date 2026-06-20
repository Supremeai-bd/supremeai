from unittest.mock import MagicMock, patch
from tools.vision_agent import VisionAgent


def test_analyze_image_success():
    agent = VisionAgent(languages=["en", "bn"])

    fake_reader = MagicMock()
    fake_reader.readtext.return_value = [
        (None, "Hello", 0.9),
        (None, "বাংলা", 0.8),
    ]

    with patch("tools.vision_agent.easyocr", create=True) as mock_easyocr:
        mock_easyocr.Reader.return_value = fake_reader
        result = agent.analyze_image("dummy.jpg")

    assert result["success"] is True
    assert result["lines"][0]["text"] == "Hello"
    assert result["lines"][1]["text"] == "বাংলা"
    assert result["structured"]["average_confidence"] > 0


def test_analyze_image_missing_easyocr():
    agent = VisionAgent()
    with patch("tools.vision_agent.easyocr", side_effect=ImportError("missing")):
        result = agent.analyze_image("dummy.jpg")

    assert result["success"] is False
    assert "error" in result


def test_analyze_pdf_no_deps():
    agent = VisionAgent()
    with patch("tools.vision_agent.fitz") as mock_fitz:
        mock_fitz.open.side_effect = ImportError("missing")
        with patch("tools.vision_agent.pdfplumber", side_effect=ImportError("missing")):
            result = agent.analyze_pdf("dummy.pdf")

    assert result["pages"] == 0
    assert result["success"] is True


def test_analyze_chart_builds_on_image_analysis():
    agent = VisionAgent()
    with patch.object(
        agent,
        "analyze_image",
        return_value={
            "success": True,
            "text": "data x:10 y:20",
            "lines": [{"text": "data x:10 y:20", "confidence": 0.9}],
            "structured": {"line_count": 1, "average_confidence": 0.9, "languages": ["en"]},
        },
    ):
        result = agent.analyze_chart("chart.png")

    assert result["structured"]["chart_hints"]
    assert result["structured"]["estimated_labels"] > 0
