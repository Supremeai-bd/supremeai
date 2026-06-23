#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> local_ocr_extractor.py
# project >> SupremeAI 2.0
# purpose >> OCR and document
# module >> tools
# ============================================================================
from typing import Any, Dict, List, Optional

from loguru import logger


class LocalOCRExtractor:
    def __init__(self, languages: Optional[List[str]] = None):
        self.languages = languages or ["en", "bn"]
        self.ocr_available = False

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        try:
            import easyocr  # type: ignore[import-untyped]
            reader = easyocr.Reader(self.languages, gpu=False)
            raw_results = reader.readtext(image_path, detail=1)
            text_lines = []
            for (_bbox, text, confidence) in raw_results:
                text_lines.append({"text": text, "confidence": confidence})
            full_text = "\n".join(item["text"] for item in text_lines)
            return {"success": True, "text": full_text, "lines": text_lines}
        except Exception as exc:
            logger.error(f"OCR failed: {exc}")
            return {"success": False, "error": str(exc), "text": ""}

    def parse_to_rows(self, text: str, columns: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            rows: List[Dict[str, Any]] = []
            for raw_line in text.splitlines():
                cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
                if columns:
                    if len(cells) == len(columns):
                        rows.append(dict(zip(columns, cells)))
                else:
                    rows.append({"data": cells})
            return {"success": True, "rows": rows, "frame": None}
        except Exception as exc:
            logger.error(f"Table parsing failed: {exc}")
            return {"success": False, "error": str(exc), "rows": []}

    def export_to_excel(self, rows: List[Dict[str, Any]], path: str) -> Dict[str, Any]:
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            if rows:
                headers = list(rows[0].keys())
                ws.append(headers)
                for row in rows:
                    ws.append([row.get(key, "") for key in headers])
            wb.save(path)
            return {"success": True, "path": path}
        except Exception as exc:
            logger.error(f"Excel export failed: {exc}")
            return {"success": False, "error": str(exc)}
