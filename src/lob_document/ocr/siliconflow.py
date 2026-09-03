from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pymupdf

from .base import CloudOcrEngine, OcrLine, OcrPageResult


class SiliconFlowOcrEngine(CloudOcrEngine):
    name = "siliconflow"

    def __init__(
        self,
        api_key: str,
        model: str = "PaddlePaddle/PaddleOCR-VL-1.5",
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout_seconds: float = 120,
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
            model=os.getenv("SILICONFLOW_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.5"),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
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
                                "Perform OCR on this document page. Return JSON only with shape "
                                '{"lines":[{"text":"...","bbox":[x0,y0,x1,y1],"confidence":0.0}]}. '
                                "Coordinates must use a 0..1000 top-left coordinate system. Preserve reading order, "
                                f"all visible text, punctuation, and the document language ({language})."
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
            parsed = json.loads(content)
            lines = [self._line(item, page.rect.width, page.rect.height) for item in parsed["lines"]]
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("SiliconFlow returned an invalid OCR JSON response") from exc
        return OcrPageResult(engine=self.name, engine_version=self.model, lines=lines)

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
