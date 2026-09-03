"""Replaceable OCR engines and execution policy."""

from .base import CloudOcrEngine, OcrEngine, OcrLine, OcrPageResult, OcrTable, OcrTableCell
from .local import TesseractOcrEngine
from .policy import OcrMode, OcrPolicy
from .siliconflow import SiliconFlowOcrEngine

__all__ = [
    "CloudOcrEngine",
    "OcrEngine",
    "OcrLine",
    "OcrMode",
    "OcrPageResult",
    "OcrTable",
    "OcrTableCell",
    "OcrPolicy",
    "SiliconFlowOcrEngine",
    "TesseractOcrEngine",
]
