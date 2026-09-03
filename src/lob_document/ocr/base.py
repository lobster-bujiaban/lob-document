from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

import pymupdf


@dataclass(frozen=True)
class OcrLine:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float | None = None


@dataclass(frozen=True)
class OcrPageResult:
    engine: str
    engine_version: str | None
    lines: list[OcrLine] = field(default_factory=list)


class OcrEngine(Protocol):
    name: str
    is_cloud: bool

    def recognize(self, page: pymupdf.Page, language: str) -> OcrPageResult: ...


class CloudOcrEngine(ABC):
    """Provider adapter boundary; implementations must declare that data leaves the machine."""

    is_cloud = True
    name: str

    @abstractmethod
    def recognize(self, page: pymupdf.Page, language: str) -> OcrPageResult:
        raise NotImplementedError
