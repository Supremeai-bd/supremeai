import json

from utils.json_helpers import json_error, json_response, json_success


class TestJsonHelpers:
    def test_json_response_preserves_objects(self):
        data = {"key": "value", "number": 42}
        result = json_response(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_json_response_ensure_ascii_false(self):
        data = {"bangla": "বাংলা", "emoji": "🎉"}
        result = json_response(data)
        assert "বাংলা" in result
        assert "🎉" in result

    def test_json_error_format(self):
        result = json_error("Something went wrong")
        parsed = json.loads(result)
        assert parsed == {"error": "Something went wrong"}

    def test_json_error_special_chars(self):
        result = json_error('Path: "C:\\Users\\n"')
        parsed = json.loads(result)
        assert parsed["error"] == 'Path: "C:\\Users\\n"'

    def test_json_success_empty_message(self):
        result = json_success()
        parsed = json.loads(result)
        assert parsed == {"success": True}

    def test_json_success_with_message(self):
        result = json_success("Operation complete")
        parsed = json.loads(result)
        assert parsed == {"success": True, "message": "Operation complete"}

    def test_json_success_with_extra_fields(self):
        result = json_success("Done", id=123, name="test")
        parsed = json.loads(result)
        assert parsed == {"success": True, "message": "Done", "id": 123, "name": "test"}

    def test_json_success_unicode(self):
        result = json_success("সফল", detail="বর্ণনা")
        parsed = json.loads(result)
        assert parsed["message"] == "সফল"
        assert parsed["detail"] == "বর্ণনা"
