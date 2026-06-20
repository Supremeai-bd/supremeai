import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from tools.video_generator import VideoGenerator

def test_video_generator_stub_fallback():
    generator = VideoGenerator(runway_api_key=None, kling_api_key=None)
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "output.json")
        res = generator.generate("A cinematic shot", duration=5, provider="runway", output_path=output_path)
        
        assert res["success"]
        assert "runway-stub" == res["provider"]
        assert res["mock"]
        assert os.path.exists(output_path)

def test_video_generator_runway_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "runway-job-123", "output": {"url": "http://runway.com/video.mp4"}}
    mock_client.post.return_value = mock_response
    
    with patch("httpx.Client", return_value=MagicMock(__enter__=MagicMock(return_value=mock_client))):
        generator = VideoGenerator(runway_api_key="key", kling_api_key=None)
        res = generator.generate("A cat dancing", provider="runway")
        
        assert res["success"]
        assert res["provider"] == "runway"
        assert res["job_id"] == "runway-job-123"
        assert res["video_url"] == "http://runway.com/video.mp4"

def test_video_generator_kling_success():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": {"task_id": "kling-job-123", "result": {"url": "http://kling.com/video.mp4"}}}
    mock_client.post.return_value = mock_response
    
    with patch("httpx.Client", return_value=MagicMock(__enter__=MagicMock(return_value=mock_client))):
        generator = VideoGenerator(runway_api_key=None, kling_api_key="key")
        res = generator.generate("A dog jumping", provider="kling")
        
        assert res["success"]
        assert res["provider"] == "kling"
        assert res["job_id"] == "kling-job-123"
        assert res["video_url"] == "http://kling.com/video.mp4"
