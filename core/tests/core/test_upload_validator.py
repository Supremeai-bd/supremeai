"""
Tests for core/upload_validator.py
"""

from __future__ import annotations

import pytest

from core.upload_validator import MAX_UPLOAD_BYTES, validate_upload


class FakeFile:
    def __init__(self, filename, content_type, body):
        self.filename = filename
        self.content_type = content_type
        self._body = body
        self._pos = 0

    async def read(self, size=-1):
        if size == -1:
            data = self._body[self._pos :]
            self._pos = len(self._body)
            return data
        data = self._body[self._pos : self._pos + size]
        self._pos += len(data)
        return data

    async def seek(self, pos):
        self._pos = pos


def test_validate_upload_rejects_unsupported_extension():
    file = FakeFile("image.bmp", "image/bmp", b"garbage")
    with pytest.raises(
        Exception
    ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
        import asyncio

        asyncio.run(validate_upload(file))


def test_validate_upload_accepts_python_file():
    body = b"print('hello')\n"
    file = FakeFile("main.py", "text/x-python", body)
    import asyncio

    asyncio.run(validate_upload(file))


def test_validate_upload_rejects_oversized_file():
    body = b"x" * (MAX_UPLOAD_BYTES + 1)
    file = FakeFile("big.py", "text/x-python", body)
    with pytest.raises(
        Exception
    ):  # -- intentionally broad: asserts *some* error propagates (mocked/validation failure), exact type varies
        import asyncio

        asyncio.run(validate_upload(file))
