from __future__ import annotations

import pymupdf

from .base import OcrLine, OcrPageResult


class TesseractOcrEngine:
    name = "tesseract"
    is_cloud = False

    def __init__(self, dpi: int = 300) -> None:
        self.dpi = dpi

    def recognize(self, page: pymupdf.Page, language: str) -> OcrPageResult:
        text_page = page.get_textpage_ocr(language=language, dpi=self.dpi, full=True)
        raw = page.get_text("dict", textpage=text_page, sort=True)
        lines: list[OcrLine] = []
        for block in raw.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                text = "".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
                if text:
                    lines.append(OcrLine(text=text, bbox=tuple(line["bbox"])))
        return OcrPageResult(engine=self.name, engine_version=None, lines=lines)
