from utils.text_helpers import strip_markdown_code_block


class TestStripMarkdownCodeBlock:
    def test_strip_code_block_python(self):
        text = "```python\nprint('hello')\n```"
        result = strip_markdown_code_block(text)
        assert result == "print('hello')"

    def test_strip_code_block_no_language(self):
        text = "```\nconsole.log('hi')\n```"
        result = strip_markdown_code_block(text)
        assert result == "console.log('hi')"

    def test_strip_no_code_block(self):
        text = "plain text without code block"
        result = strip_markdown_code_block(text)
        assert result == "plain text without code block"

    def test_strip_only_closing_fence(self):
        text = "```python\ncode here"
        result = strip_markdown_code_block(text)
        assert result == "code here"

    def test_strip_nested_fences(self):
        text = '```json\n{"inner": "```not a fence```"}\n```'
        result = strip_markdown_code_block(text)
        assert result == '{"inner": "```not a fence```"}'

    def test_strip_empty_after_fences(self):
        text = "```\n```"
        result = strip_markdown_code_block(text)
        assert result == ""

    def test_strip_leading_trailing_whitespace(self):
        text = "  ```python\n  hello\n  ```  "
        result = strip_markdown_code_block(text)
        assert result == "hello"

    def test_strip_multiline_with_blank_lines(self):
        text = "```python\nline1\n\nline2\n```"
        result = strip_markdown_code_block(text)
        assert result == "line1\n\nline2"
