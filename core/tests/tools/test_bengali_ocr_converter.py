"""Tests for tools/localization/bengali_ocr_converter.py — the Bengali OCR →
Excel conversion pipeline.

Covers the Google-Vision client bootstrap ladder, the text-extraction flow
with its resilient local-OCR fallback, the tabular text parser, the full
image → xlsx conversion (REAL pandas + openpyxl round-trip: the written
workbook is read back and asserted), and the batch folder walker.

Honesty boundaries: google.cloud.vision is not installed in the test
environment, so the "installed" path is simulated by monkeypatching the
module globals (HAS_GOOGLE_VISION / vision) with a scripted fake — the
network boundary. The LocalOCRExtractor fallback boundary is likewise
scripted (the real engine needs the easyocr/tesseract binaries).
pandas, openpyxl and all file I/O are REAL.
"""

from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace

import pytest

import backend.tools.localization.bengali_ocr_converter as boc

try:
    # CI parity: pandas is an optional dependency for this module (the owner's
    # try/except keeps the converter importable without it). Mirror that here
    # so collection never fails on environments without pandas; the
    # pandas-dependent tests gate themselves below.
    import pandas as pd
except ImportError:  # pragma: no cover - depends on environment
    pd = None

from backend.tools.localization.bengali_ocr_converter import (
    batch_convert_images,
    convert_image_to_excel,
    extract_text_from_image,
    parse_table_text,
    setup_google_vision,
)

PANDAS_REASON = "pandas not installed in this environment"

# ─────────────────────────────────────────────────────────────────────────────
# Fakes for the google.cloud.vision boundary
# ─────────────────────────────────────────────────────────────────────────────


class FakeVisionNamespace:
    """Stands in for the google.cloud.vision module namespace."""

    def __init__(self, client_factory):
        self._client_factory = client_factory
        self.image_calls: list[dict] = []
        self.clients_built: list[dict] = []

    def Image(self, content=None):
        self.image_calls.append({"content": content})
        return {"kind": "image", "content": content}

    def ImageContext(self, language_hints=None):
        return {"kind": "context", "language_hints": language_hints}

    def ImageAnnotatorClient(self, credentials=None):
        self.clients_built.append({"credentials": credentials})
        return self._client_factory(credentials=credentials)


class FakeCredentialsNamespace:
    def __init__(self, loaded):
        self.loaded = loaded
        self.fail = False

    class Credentials:
        @staticmethod
        def from_service_account_file(path):
            return {"loaded_from": path}


class FakeVisionClient:
    def __init__(self, descriptions=None, error_message="", raise_exc=None):
        self.descriptions = descriptions or []
        self.error_message = error_message
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def text_detection(self, image=None, image_context=None):
        self.calls.append({"image": image, "image_context": image_context})
        if self.raise_exc is not None:
            raise self.raise_exc
        return SimpleNamespace(
            text_annotations=[SimpleNamespace(description=d) for d in self.descriptions],
            error=SimpleNamespace(message=self.error_message),
        )


def install_vision(monkeypatch, client, credentials_ns=None):
    ns = FakeVisionNamespace(lambda credentials=None: client)
    monkeypatch.setattr(boc, "vision", ns)
    monkeypatch.setattr(boc, "HAS_GOOGLE_VISION", True)
    monkeypatch.setattr(
        boc,
        "service_account",
        credentials_ns if credentials_ns is not None else FakeCredentialsNamespace(None),
    )
    return ns


def install_local_extractor(monkeypatch, result=None, raise_exc=None):
    """Patch the LocalOCRExtractor the function imports at call time.

    The function does `from tools.localization.local_ocr_extractor import
    LocalOCRExtractor` (top-level alias) — patch BOTH aliases for runner
    robustness (module-object aliasing gotcha).
    """
    import importlib

    calls: list[dict] = []

    class FakeExtractor:
        def __init__(self, languages=None):
            calls.append({"languages": languages})

        def extract_text(self, image_path):
            if raise_exc is not None:
                raise raise_exc
            return dict(result or {})

    for name in (
        "tools.localization.local_ocr_extractor",
        "backend.tools.localization.local_ocr_extractor",
    ):
        try:
            mod = importlib.import_module(name)
        except Exception:  # pragma: no cover - alias unavailable in some runners
            continue
        monkeypatch.setattr(mod, "LocalOCRExtractor", FakeExtractor)
    return calls


# ─────────────────────────────────────────────────────────────────────────────
# setup_google_vision — bootstrap ladder
# ─────────────────────────────────────────────────────────────────────────────


class TestSetupGoogleVision:
    def test_returns_none_when_vision_unavailable(self, monkeypatch):
        monkeypatch.setattr(boc, "HAS_GOOGLE_VISION", False)
        assert setup_google_vision() is None

    def test_default_client_without_credentials(self, monkeypatch):
        client = FakeVisionClient()
        ns = install_vision(monkeypatch, client)
        result = setup_google_vision()
        assert result is client
        assert ns.clients_built == [{"credentials": None}]

    def test_client_with_service_account_file(self, monkeypatch):
        client = FakeVisionClient()
        ns = install_vision(monkeypatch, client)
        result = setup_google_vision(credentials_path="/tmp/sa-key.json")
        assert result is client
        assert ns.clients_built == [{"credentials": {"loaded_from": "/tmp/sa-key.json"}}]

    def test_client_construction_failure_returns_none(self, monkeypatch):
        def exploding_factory(credentials=None):
            raise RuntimeError("quota/billing not enabled")

        ns = FakeVisionNamespace(exploding_factory)
        monkeypatch.setattr(boc, "vision", ns)
        monkeypatch.setattr(boc, "HAS_GOOGLE_VISION", True)
        assert setup_google_vision() is None
        assert ns.clients_built == [{"credentials": None}]


# ─────────────────────────────────────────────────────────────────────────────
# extract_text_from_image — vision flow + local fallback
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTextFromImage:
    def test_missing_image_path_returns_empty(self, monkeypatch, tmp_path):
        assert extract_text_from_image(None, str(tmp_path / "ghost.png")) == ""

    def test_vision_success_returns_first_description(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"png-bytes-here")
        client = FakeVisionClient(descriptions=["বাংলা OCR output line"])
        ns = install_vision(monkeypatch, client)
        result = extract_text_from_image(client, str(img))
        assert result == "বাংলা OCR output line"
        # Bengali language hint flows through the image context
        assert ns.image_calls[0]["content"] == b"png-bytes-here"
        assert client.calls[0]["image_context"] == {
            "kind": "context",
            "language_hints": ["bn"],
        }

    def test_no_texts_returns_empty_without_fallback(self, monkeypatch, tmp_path):
        img = tmp_path / "blank.png"
        img.write_bytes(b"x")
        client = FakeVisionClient(descriptions=[])
        install_vision(monkeypatch, client)
        calls = install_local_extractor(monkeypatch, result={"text": "should-not-be-used"})
        assert extract_text_from_image(client, str(img)) == ""
        assert calls == []  # empty annotations short-circuit — no local fallback

    def test_api_error_message_raises_then_falls_back(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"x")
        client = FakeVisionClient(error_message="Permission denied on project")
        install_vision(monkeypatch, client)
        calls = install_local_extractor(monkeypatch, result={"text": "local-text"})
        assert extract_text_from_image(client, str(img)) == "local-text"
        assert calls[0]["languages"] == ["bn", "en"]

    def test_vision_transport_failure_falls_back(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"x")
        client = FakeVisionClient(raise_exc=RuntimeError("503 backend error"))
        install_vision(monkeypatch, client)
        install_local_extractor(monkeypatch, result={"text": "fallback-ok"})
        assert extract_text_from_image(client, str(img)) == "fallback-ok"

    def test_client_none_goes_straight_to_local(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"x")
        monkeypatch.setattr(boc, "HAS_GOOGLE_VISION", True)  # even with vision present
        calls = install_local_extractor(monkeypatch, result={"text": "no-client-path"})
        assert extract_text_from_image(None, str(img)) == "no-client-path"
        assert calls[0]["languages"] == ["bn", "en"]

    def test_local_result_without_text_key_yields_empty(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"x")
        install_local_extractor(monkeypatch, result={"rows": 3})  # no "text" key
        assert extract_text_from_image(None, str(img)) == ""

    def test_local_extractor_crash_yields_empty(self, monkeypatch, tmp_path):
        img = tmp_path / "scan.png"
        img.write_bytes(b"x")
        install_local_extractor(monkeypatch, raise_exc=ImportError("easyocr missing"))
        assert extract_text_from_image(None, str(img)) == ""

    def test_missing_path_short_circuits_before_client(self, monkeypatch, tmp_path):
        client = FakeVisionClient(descriptions=["x"])
        install_vision(monkeypatch, client)
        calls = install_local_extractor(monkeypatch, result={"text": "y"})
        assert extract_text_from_image(client, str(tmp_path / "nope.png")) == ""
        assert calls == []


# ─────────────────────────────────────────────────────────────────────────────
# parse_table_text — tabular text splitting
# ─────────────────────────────────────────────────────────────────────────────


class TestParseTableText:
    def test_tab_separated_cells(self):
        assert parse_table_text("name\tqty\nrice\t2") == [["name", "qty"], ["rice", "2"]]

    def test_multi_space_separated_cells(self):
        assert parse_table_text("item    price\nmilk    50") == [
            ["item", "price"],
            ["milk", "50"],
        ]

    def test_blank_lines_skipped(self):
        assert parse_table_text("\n\na  b\n\n\nc  d\n") == [["a", "b"], ["c", "d"]]

    def test_empty_text_returns_empty_list(self):
        assert parse_table_text("") == []

    def test_whitespace_only_text_returns_empty_list(self):
        assert parse_table_text("   \n  \t \n") == []

    def test_single_word_line_is_single_cell(self):
        assert parse_table_text("lonely") == [["lonely"]]

    def test_bengali_characters_preserved(self):
        table = parse_table_text("পণ্য    দাম\nচাল    ৫০")
        assert table == [["পণ্য", "দাম"], ["চাল", "৫০"]]

    def test_line_with_no_separator_is_one_cell(self):
        assert parse_table_text("just one chunk") == [["just one chunk"]]


# ─────────────────────────────────────────────────────────────────────────────
# convert_image_to_excel — REAL pandas + openpyxl round-trip
# ─────────────────────────────────────────────────────────────────────────────


def read_sheet(xlsx_path: str, sheet: str, **kwargs) -> pd.DataFrame:
    return pd.read_excel(xlsx_path, sheet_name=sheet, engine="openpyxl", **kwargs)


xlsx_test = pytest.mark.skipif(pd is None, reason=PANDAS_REASON)


class TestConvertImageToExcel:
    @xlsx_test
    def test_table_text_produces_two_sheet_workbook(self, monkeypatch, tmp_path):
        img = tmp_path / "invoice.png"
        img.write_bytes(b"x")
        excel = tmp_path / "invoice.xlsx"
        client = FakeVisionClient(
            descriptions=["Item    Qty    Price\nRice    2    120\nMilk    1"]
        )
        install_vision(monkeypatch, client)
        assert convert_image_to_excel(str(img), str(excel), client) is True
        assert excel.exists()

        meta = read_sheet(str(excel), "Metadata")
        meta_map = dict(zip(meta["Property"], meta["Value"], strict=True))
        assert meta_map["Image_File"] == "invoice.png"
        assert meta_map["Text_Length"] == len("Item    Qty    Price\nRice    2    120\nMilk    1")
        assert meta_map["Table_Rows"] == 3
        assert meta_map["Table_Columns"] == 3

        data = read_sheet(str(excel), "Data", header=None)
        # Row 0 is the integer header row pandas writes (DataFrame columns 0/1/2).
        assert data.shape[0] == 4
        assert str(data.iloc[1, 0]) == "Item" and str(data.iloc[1, 2]) == "Price"
        assert str(data.iloc[3, 0]) == "Milk" and str(data.iloc[3, 1]) == "1"
        # ragged last row padded to 3 columns (Milk has no Price cell)
        assert pd.isna(data.iloc[3, 2]) or str(data.iloc[3, 2]) in ("", "nan", "None")

    @xlsx_test
    def test_ragged_rows_padded_to_max_columns(self, monkeypatch, tmp_path):
        img = tmp_path / "r.png"
        img.write_bytes(b"x")
        excel = tmp_path / "r.xlsx"
        client = FakeVisionClient(descriptions=["a    b    c\nd    e"])
        install_vision(monkeypatch, client)
        assert convert_image_to_excel(str(img), str(excel), client) is True
        data = read_sheet(str(excel), "Data", header=None)
        assert data.shape == (3, 3)  # header row + 2 data rows
        assert str(data.iloc[2, 2]) in ("", "nan", "None") or pd.isna(data.iloc[2, 2])

    @xlsx_test
    def test_whitespace_text_uses_raw_text_fallback_sheet(self, monkeypatch, tmp_path):
        # Text that is non-empty but parses to zero rows (newlines/whitespace
        # only) takes the raw-text DataFrame branch and still produces a file.
        img = tmp_path / "raw.png"
        img.write_bytes(b"x")
        excel = tmp_path / "raw.xlsx"
        client = FakeVisionClient(descriptions=["\n  \n"])
        install_vision(monkeypatch, client)
        assert convert_image_to_excel(str(img), str(excel), client) is True
        assert excel.exists()
        meta = read_sheet(str(excel), "Metadata")
        meta_map = dict(zip(meta["Property"], meta["Value"], strict=True))
        assert meta_map["Table_Rows"] == 0
        assert meta_map["Table_Columns"] == 1
        data = read_sheet(str(excel), "Data")
        assert list(data.columns) == ["Extracted_Text"]

    def test_whitespace_only_extraction_returns_false(self, monkeypatch, tmp_path):
        img = tmp_path / "w.png"
        img.write_bytes(b"x")
        client = FakeVisionClient(descriptions=[])
        install_vision(monkeypatch, client)
        assert convert_image_to_excel(str(img), str(tmp_path / "w.xlsx"), client) is False

    def test_missing_image_returns_false(self, monkeypatch, tmp_path):
        assert (
            convert_image_to_excel(str(tmp_path / "ghost.png"), str(tmp_path / "g.xlsx"), None)
            is False
        )

    @xlsx_test
    def test_excel_write_oserror_is_caught(self, monkeypatch, tmp_path):
        img = tmp_path / "ok.png"
        img.write_bytes(b"x")
        client = FakeVisionClient(descriptions=["col1    col2"])
        install_vision(monkeypatch, client)
        # unwritable target directory -> OSError from ExcelWriter -> caught
        bad_dir = tmp_path / "no-such-dir"
        assert convert_image_to_excel(str(img), str(bad_dir / "out.xlsx"), client) is False

    def test_extractor_crash_surface_is_limited_to_known_exceptions(self, monkeypatch, tmp_path):
        # convert_image_to_excel only catches (OSError, ValueError, RuntimeError);
        # an unexpected error type propagates by design (Bengali comment in
        # source: avoid swallowing unrelated failures). Document that contract.
        img = tmp_path / "c.png"
        img.write_bytes(b"x")
        excel = tmp_path / "c.xlsx"
        client = FakeVisionClient(descriptions=["a  b"])
        install_vision(monkeypatch, client)

        def explode(*args, **kwargs):
            raise ZeroDivisionError("unexpected bug class")

        monkeypatch.setattr(boc, "parse_table_text", explode)
        with pytest.raises(ZeroDivisionError):
            convert_image_to_excel(str(img), str(excel), client)

    @xlsx_test
    def test_local_fallback_text_converts_to_excel(self, monkeypatch, tmp_path):
        img = tmp_path / "fb.png"
        img.write_bytes(b"x")
        excel = tmp_path / "fb.xlsx"
        client = FakeVisionClient(error_message="quota exceeded")  # forces fallback
        install_vision(monkeypatch, client)
        install_local_extractor(monkeypatch, result={"text": "নাম    মান\nস্কোর    ৯৯"})
        assert convert_image_to_excel(str(img), str(excel), client) is True
        data = read_sheet(str(excel), "Data", header=None)
        assert str(data.iloc[2, 0]) == "স্কোর"
        assert str(data.iloc[2, 1]) == "৯৯"


# ─────────────────────────────────────────────────────────────────────────────
# batch_convert_images — folder walker
# ─────────────────────────────────────────────────────────────────────────────


class SequentialVisionClient(FakeVisionClient):
    """Vision client whose annotations vary per text_detection call."""

    def __init__(self, per_call_descriptions):
        super().__init__(descriptions=[])
        self.per_call = list(per_call_descriptions)

    def text_detection(self, image=None, image_context=None):
        self.calls.append({"image": image, "image_context": image_context})
        desc = self.per_call.pop(0) if self.per_call else []
        return SimpleNamespace(
            text_annotations=[SimpleNamespace(description=d) for d in desc],
            error=SimpleNamespace(message=""),
        )


class TestBatchConvertImages:
    @xlsx_test
    def test_converts_jpg_files_sorted_with_xlsx_outputs(self, monkeypatch, tmp_path):
        (tmp_path / "b.jpg").write_bytes(b"x")
        (tmp_path / "a.jpg").write_bytes(b"x")
        (tmp_path / "c.png").write_bytes(b"x")  # ignored
        (tmp_path / "notes.txt").write_text("ignored")

        client = FakeVisionClient(descriptions=["h    v"])
        install_vision(monkeypatch, client)
        monkeypatch.setattr(boc, "setup_google_vision", lambda creds=None: client)

        batch_convert_images(str(tmp_path))

        assert (tmp_path / "a_vision.xlsx").exists()
        assert (tmp_path / "b_vision.xlsx").exists()
        assert not (tmp_path / "c_vision.xlsx").exists()

    @xlsx_test
    def test_uppercase_jpg_extension_included(self, monkeypatch, tmp_path):
        (tmp_path / "UPPER.JPG").write_bytes(b"x")
        client = FakeVisionClient(descriptions=["k    v"])
        install_vision(monkeypatch, client)
        monkeypatch.setattr(boc, "setup_google_vision", lambda creds=None: client)
        batch_convert_images(str(tmp_path))
        assert (tmp_path / "UPPER_vision.xlsx").exists()

    @xlsx_test
    def test_empty_text_files_not_counted(self, monkeypatch, tmp_path):
        (tmp_path / "good.jpg").write_bytes(b"x")
        (tmp_path / "empty.jpg").write_bytes(b"x")
        # sorted order: empty.jpg is processed FIRST, then good.jpg
        client = SequentialVisionClient([[], ["h    v"]])
        install_vision(monkeypatch, client)
        monkeypatch.setattr(boc, "setup_google_vision", lambda creds=None: client)
        batch_convert_images(str(tmp_path))
        assert (tmp_path / "good_vision.xlsx").exists()
        assert not (tmp_path / "empty_vision.xlsx").exists()
        assert len(client.calls) == 2  # both images attempted

    def test_empty_folder_processes_zero_images(self, monkeypatch, tmp_path):
        monkeypatch.setattr(boc, "setup_google_vision", lambda creds=None: None)
        batch_convert_images(str(tmp_path))  # no crash, nothing produced
        assert list(tmp_path.glob("*.xlsx")) == []

    def test_missing_folder_raises_file_not_found(self, monkeypatch, tmp_path):
        # Documented contract: the walker does not guard os.listdir; the CLI
        # entrypoint (__main__) is the guard. Wire-first — no behavior change.
        monkeypatch.setattr(boc, "setup_google_vision", lambda creds=None: None)
        with pytest.raises(FileNotFoundError):
            batch_convert_images(str(tmp_path / "no-such-folder"))

    @xlsx_test
    def test_credentials_path_forwarded_to_setup(self, monkeypatch, tmp_path):
        seen: dict = {}
        client = FakeVisionClient(descriptions=["a    b"])

        def fake_setup(creds=None):
            seen["creds"] = creds
            return client

        (tmp_path / "x.jpg").write_bytes(b"x")
        monkeypatch.setattr(boc, "setup_google_vision", fake_setup)
        batch_convert_images(str(tmp_path), credentials_path="/keys/sa.json")
        assert seen["creds"] == "/keys/sa.json"


# ─────────────────────────────────────────────────────────────────────────────
# Module import-time degradation arms — exercised via controlled reload
# ─────────────────────────────────────────────────────────────────────────────


def _fake_google_stack():
    """Build fake google.cloud.vision / google.oauth2.service_account modules."""
    fake_gvision = types.ModuleType("google.cloud.vision")
    fake_sa = types.ModuleType("google.oauth2.service_account")
    fake_oauth2 = types.ModuleType("google.oauth2")
    fake_cloud = types.ModuleType("google.cloud")
    fake_google = types.ModuleType("google")
    fake_cloud.vision = fake_gvision
    fake_oauth2.service_account = fake_sa
    return fake_google, fake_cloud, fake_gvision, fake_oauth2, fake_sa


_RESTORE_KEYS = (
    "pandas",
    "google",
    "google.cloud",
    "google.cloud.vision",
    "google.oauth2",
    "google.oauth2.service_account",
)

_ABSENT = object()  # sentinel: key was NOT in sys.modules before the reload


class TestModuleImportDegradation:
    """The module degrades gracefully at IMPORT time when optional deps are
    absent (pd=None / HAS_GOOGLE_VISION=False). These arms are unreachable in
    an environment where pandas is installed, so they are exercised by
    reloading the module under controlled sys.modules conditions — with a
    guaranteed restore so every other test sees the pristine module."""

    def _reload_capture_state_under(self, overrides):
        """Reload the module with sys.modules[key] forced to the given values.

        Setting None in sys.modules makes the import machinery raise
        ImportError for that module — exactly the degradation arm under test.
        Returns a SNAPSHOT of the module state taken mid-degradation (the
        finally-block restore reload mutates the same module object in place,
        so a live reference would show restored state by the time the caller
        inspects it).
        """
        import importlib

        snapshot = {}
        # Distinguish "key absent" from "key present but None" (None in
        # sys.modules is itself a legitimate blocked-import state).
        saved = {k: (sys.modules[k] if k in sys.modules else _ABSENT) for k in _RESTORE_KEYS}
        try:
            for k, v in overrides.items():
                sys.modules[k] = v
            reloaded = importlib.reload(boc)
            snapshot["pd"] = reloaded.pd
            snapshot["HAS_GOOGLE_VISION"] = reloaded.HAS_GOOGLE_VISION
            snapshot["vision"] = reloaded.vision
            snapshot["service_account"] = reloaded.service_account
        finally:
            for k, v in saved.items():
                if v is _ABSENT:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
            importlib.reload(boc)  # restore pristine module state
        return snapshot

    def test_pandas_missing_degrades_to_pd_none_with_vision_present(self):
        fake_google, fake_cloud, fake_gvision, fake_oauth2, fake_sa = _fake_google_stack()
        snap = self._reload_capture_state_under(
            {
                "pandas": None,  # None in sys.modules -> import raises ImportError
                "google": fake_google,
                "google.cloud": fake_cloud,
                "google.cloud.vision": fake_gvision,
                "google.oauth2": fake_oauth2,
                "google.oauth2.service_account": fake_sa,
            }
        )
        assert snap["pd"] is None
        assert snap["HAS_GOOGLE_VISION"] is True
        assert snap["vision"] is fake_gvision
        assert snap["service_account"] is fake_sa

    def test_vision_missing_degrades_flag_but_keeps_pandas(self):
        snap = self._reload_capture_state_under(
            {k: None for k in _RESTORE_KEYS if k.startswith("google")}
        )
        assert snap["HAS_GOOGLE_VISION"] is False
        assert snap["vision"] is None
        assert snap["service_account"] is None
        assert snap["pd"] is pd  # real pandas untouched

    def test_pristine_state_restored_after_degradation_reload(self):
        # The helper's finally-reload must leave the module exactly as found.
        assert boc.pd is pd
        assert boc.HAS_GOOGLE_VISION is False  # google-cloud-vision not installed here
