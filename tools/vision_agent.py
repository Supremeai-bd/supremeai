#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> vision_agent.py
# project >> SupremeAI 2.0
# purpose >> AI agent management
# module >> tools
# ============================================================================
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger


class VisionAgent:
    def __init__(self, languages: Optional[List[str]] = None) -> None:
        self.languages = languages or ["en", "bn"]

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        try:
            import easyocr  # type: ignore[import-untyped]
        except Exception as exc:
            logger.error(f"EasyOCR is not available: {exc}")
            return {"success": False, "error": str(exc), "text": "", "structured": {}}

        reader: Optional[Any] = None
        try:
            reader = easyocr.Reader(self.languages, gpu=False)
            raw_results = reader.readtext(image_path, detail=1, paragraph=False)
            text_lines = [
                {"text": text, "confidence": confidence}
                for (_bbox, text, confidence) in raw_results
            ]
            full_text = "\n".join(item["text"] for item in text_lines)
            return {
                "success": True,
                "text": full_text,
                "lines": text_lines,
                "structured": self._structure(text_lines),
            }
        except Exception as exc:
            logger.error(f"Vision image analysis failed: {exc}")
            return {"success": False, "error": str(exc), "text": "", "structured": {}}

    def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        try:
            text_pages = self._extract_pdf_text(pdf_path)
            cover_text = self._summarize(text_pages[:2]) if text_pages else ""
            return {
                "success": True,
                "path": pdf_path,
                "pages": len(text_pages),
                "text": "\n\n".join(text_pages),
                "summary": cover_text,
                "structured": {"pages": len(text_pages)},
            }
        except Exception as exc:
            logger.error(f"Vision PDF analysis failed: {exc}")
            return {"success": False, "error": str(exc), "text": "", "structured": {}}

    def analyze_chart(self, image_path: str) -> Dict[str, Any]:
        result = self.analyze_image(image_path)
        if not result.get("success"):
            return result
        lines = result.get("lines", [])
        chart_hints = [ln["text"] for ln in lines if any(k in ln["text"].lower() for k in ["data", "axis", "value", "x:", "y:", "legend", "label"])]
        structured = dict(result.get("structured", {}))
        structured.update({"chart_hints": chart_hints, "estimated_labels": len(chart_hints)})
        return {"success": True, "text": result["text"], "lines": lines, "structured": structured}

    @staticmethod
    def _structure(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        entry = {
            "line_count": len(lines),
            "average_confidence": 0.0,
            "languages": ["en"],
        }
        if not lines:
            return entry
        confidences = [ln["confidence"] for ln in lines]
        entry["average_confidence"] = round(sum(confidences) / len(confidences), 4)
        return entry

    @staticmethod
    def _extract_pdf_text(pdf_path: str) -> List[str]:
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            return [page.get_text("text") for page in doc if not page.is_closed]
        except ImportError:
            pass
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return pages
        except ImportError:
            pass
        logger.warning("Neither PyMuPDF nor pdfplumber is available for PDF extraction.")
        stub_path = os.path.splitext(pdf_path)[0] + ".txt"
        if os.path.exists(stub_path):
            with open(stub_path, "r", encoding="utf-8") as f:
                return [f.read()]
        return [f"[stub] PDF text extraction unavailable for: {pdf_path}"]

    @staticmethod
    def _summarize(texts: List[str]) -> str:
        joined = " ".join(texts).strip()
        return joined[:800] + ("..." if len(joined) > 800 else "")
