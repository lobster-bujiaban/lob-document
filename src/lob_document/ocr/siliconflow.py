from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pymupdf

from .base import CloudOcrEngine, OcrLine, OcrPageResult, OcrTable, OcrTableCell


class SiliconFlowOcrEngine(CloudOcrEngine):
    name = "siliconflow"

    def __init__(
        self,
        api_key: str,
        model: str = "Qwen/Qwen3-VL-8B-Instruct",
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout_seconds: float = 300,
        dpi: int = 200,
    ) -> None:
        if not api_key.strip():
            raise ValueError("SILICONFLOW_API_KEY is missing; set it in .env")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.dpi = dpi

    @classmethod
    def from_env(cls) -> SiliconFlowOcrEngine:
        return cls(
            api_key=os.getenv("SILICONFLOW_API_KEY", ""),
            model=os.getenv("SILICONFLOW_OCR_MODEL", "Qwen/Qwen3-VL-8B-Instruct"),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
            timeout_seconds=float(os.getenv("SILICONFLOW_TIMEOUT_SECONDS", "300")),
        )

    def recognize(self, page: pymupdf.Page, language: str) -> OcrPageResult:
        pixmap = page.get_pixmap(dpi=self.dpi, alpha=False)
        image = base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=88)).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image}", "detail": "high"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Perform OCR and recover tables on this document page. Return JSON only with shape "
                                '{"lines":[{"text":"...","bbox":[x0,y0,x1,y1],"confidence":0.0}],'
                                '"tables":[{"bbox":[x0,y0,x1,y1],"rows":[["cell 0,0","cell 0,1"],'
                                '["cell 1,0","cell 1,1"]],"merged_cells":[{"row":0,"column":0,'
                                '"row_span":1,"column_span":2}]}]}. '
                                "Coordinates must use a 0..1000 top-left coordinate system. Preserve reading order, "
                                "every row must have the same number of columns, use empty strings for empty or covered cells, "
                                "and include text inside tables in both lines and rows. "
                                f"Preserve all visible text, punctuation, and the document language ({language})."
                            ),
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 8192,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"SiliconFlow HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"SiliconFlow request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
            normalized = content.strip()
            if normalized.startswith("```"):
                normalized = normalized.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(normalized)
            lines = [self._line(item, page.rect.width, page.rect.height) for item in parsed["lines"]]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("SiliconFlow returned an invalid OCR JSON response") from exc
        tables = []
        for item in parsed.get("tables", []):
            try:
                tables.append(self._table(item, page.rect.width, page.rect.height))
            except (KeyError, TypeError, ValueError):
                continue
        return OcrPageResult(engine=self.name, engine_version=self.model, lines=lines, tables=tables)

    @staticmethod
    def _line(item: object, width: float, height: float) -> OcrLine:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ValueError("invalid OCR line")
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("invalid OCR bounding box")
        values = [min(1000.0, max(0.0, float(value))) for value in bbox]
        if values[2] < values[0] or values[3] < values[1]:
            raise ValueError("invalid OCR bounding box extents")
        confidence = item.get("confidence")
        normalized_confidence = None if confidence is None else min(1.0, max(0.0, float(confidence)))
        return OcrLine(
            text=item["text"],
            bbox=(values[0] * width / 1000, values[1] * height / 1000, values[2] * width / 1000, values[3] * height / 1000),
            confidence=normalized_confidence,
        )

    @staticmethod
    def _coordinates(value: object, width: float, height: float) -> tuple[float, float, float, float]:
        if not isinstance(value, list) or len(value) != 4:
            raise ValueError("invalid OCR bounding box")
        values = [min(1000.0, max(0.0, float(item))) for item in value]
        if values[2] < values[0] or values[3] < values[1]:
            raise ValueError("invalid OCR bounding box extents")
        return values[0] * width / 1000, values[1] * height / 1000, values[2] * width / 1000, values[3] * height / 1000

    @classmethod
    def _table(cls, item: object, width: float, height: float) -> OcrTable:
        if not isinstance(item, dict):
            raise ValueError("invalid OCR table")
        raw_cells = item.get("cells", [])
        table_bbox = cls._coordinates(item["bbox"], width, height)
        cells = []
        rows = item.get("rows")
        if isinstance(rows, list) and rows:
            column_count = max((len(row) for row in rows if isinstance(row, list)), default=0)
            merges = {
                (int(merge.get("row", 0)), int(merge.get("column", 0))): merge
                for merge in item.get("merged_cells", [])
                if isinstance(merge, dict)
            }
            for row_index, row in enumerate(rows):
                if not isinstance(row, list):
                    continue
                for column_index in range(column_count):
                    merge = merges.get((row_index, column_index), {})
                    cells.append(
                        OcrTableCell(
                            row=row_index,
                            column=column_index,
                            row_span=max(1, int(merge.get("row_span", 1))),
                            column_span=max(1, int(merge.get("column_span", 1))),
                            text=str(row[column_index] if column_index < len(row) else ""),
                            bbox=table_bbox,
                        )
                    )
        elif isinstance(raw_cells, list):
            for cell in raw_cells:
                if not isinstance(cell, dict) or "row" not in cell or "column" not in cell:
                    continue
                confidence = cell.get("confidence")
                cells.append(
                    OcrTableCell(
                        row=int(cell["row"]),
                        column=int(cell["column"]),
                        row_span=max(1, int(cell.get("row_span", 1))),
                        column_span=max(1, int(cell.get("column_span", cell.get("col_span", 1)))),
                        text=str(cell.get("text", "")),
                        bbox=cls._coordinates(cell["bbox"], width, height) if cell.get("bbox") else table_bbox,
                        confidence=None if confidence is None else min(1.0, max(0.0, float(confidence))),
                    )
                )
        if not cells:
            raise ValueError("OCR table has no valid cells")
        row_count = max(cell.row + cell.row_span for cell in cells)
        column_count = max(cell.column + cell.column_span for cell in cells)
        if row_count < 1 or column_count < 1:
            raise ValueError("invalid OCR table dimensions")
        return OcrTable(
            bbox=table_bbox,
            row_count=row_count,
            column_count=column_count,
            cells=cells,
        )
