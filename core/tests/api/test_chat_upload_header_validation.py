"""Chat image-upload signature validation (audit item ⑭ + residual).

``_validate_image_header`` is the only thing standing between "declared an image"
and "written to disk under an image extension". Two defects were closed in the
audit pass and pinned here:

* AVIF/TIFF used to be trusted on the declared MIME type alone (no bytes check);
* every type that reached the end of the function returned ``True`` — a free pass
  for any future entry in ``ALLOWED_MIME_TYPES`` without a signature check.

SVG must be parsed with ``defusedxml``; if that import is unavailable the upload
is rejected rather than parsed with a billion-laughs-capable parser.
"""

from __future__ import annotations

import pytest

from core.api.routes.chat_upload import ALLOWED_MIME_TYPES, _validate_image_header

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32
BMP = b"BM" + b"\x00" * 32
AVIF = b"\x00\x00\x00\x20ftypavif" + b"\x00" * 32
TIFF_LE = b"II*\x00" + b"\x00" * 32
TIFF_BE = b"MM\x00*" + b"\x00" * 32
SVG_SAFE = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'


@pytest.mark.parametrize(
    ("mime_type", "content"),
    [
        ("image/png", PNG),
        ("image/jpeg", JPEG),
        ("image/gif", GIF),
        ("image/webp", WEBP),
        ("image/bmp", BMP),
        ("image/avif", AVIF),
        ("image/tiff", TIFF_LE),
        ("image/tiff", TIFF_BE),
        ("image/svg+xml", SVG_SAFE),
    ],
)
def test_real_signatures_pass(mime_type, content):
    assert _validate_image_header(content, mime_type) is True


@pytest.mark.parametrize(
    ("mime_type", "content"),
    [
        ("image/png", b"<script>alert(1)</script>"),
        ("image/jpeg", PNG),
        ("image/gif", b"not a gif"),
        ("image/avif", b"\x00\x00\x00\x20ftypisom"),  # ISO-BMFF, wrong brand
        ("image/tiff", b"NOTATIFF"),
        ("image/svg+xml", b'<svg><script>alert(1)</script></svg>'),
        ("image/svg+xml", b'<svg onload="alert(1)"/>'),
        ("image/svg+xml", b'<svg><foreignObject><body/></foreignObject></svg>'),
        ("image/svg+xml", b"<svg>"),  # malformed
    ],
)
def test_spoofed_or_dangerous_payloads_are_rejected(mime_type, content):
    assert _validate_image_header(content, mime_type) is False


def test_unknown_mime_fails_closed(monkeypatch):
    """The old ``return True`` fallthrough — the residual ⑭ finding."""
    assert _validate_image_header(PNG, "image/avif-sequence") is False
    assert _validate_image_header(PNG, "") is False
    assert _validate_image_header(PNG, "image/heic") is False


def test_every_allowed_mime_type_has_a_signature_check():
    """A new ALLOWED_MIME_TYPES entry without a check must not become a free pass.

    ``_validate_image_header`` returns False for anything it does not recognise,
    so this test documents the invariant: add the type *and* its signature check
    together.
    """
    samples = {
        "image/jpeg": JPEG,
        "image/png": PNG,
        "image/gif": GIF,
        "image/webp": WEBP,
        "image/svg+xml": SVG_SAFE,
        "image/bmp": BMP,
        "image/tiff": TIFF_LE,
        "image/avif": AVIF,
    }
    for mime_type in ALLOWED_MIME_TYPES:
        assert mime_type in samples, (
            f"{mime_type} is allowed for upload but has no signature sample here — "
            "add one and implement its check in _validate_image_header"
        )
        assert _validate_image_header(samples[mime_type], mime_type) is True


def test_svg_upload_rejected_when_defusedxml_missing(monkeypatch):
    """Fail closed: no defusedxml → SVG uploads are refused, never parsed."""
    import builtins
    import sys

    real_import = builtins.__import__

    def _no_defusedxml(name, *args, **kwargs):
        if name.startswith("defusedxml"):
            raise ImportError("defusedxml not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_defusedxml)
    monkeypatch.delitem(sys.modules, "defusedxml", raising=False)
    monkeypatch.delitem(sys.modules, "defusedxml.ElementTree", raising=False)
    assert _validate_image_header(SVG_SAFE, "image/svg+xml") is False
