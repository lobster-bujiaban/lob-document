from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OcrMode(StrEnum):
    AUTO = "auto"
    NEVER = "never"
    ALWAYS = "always"


@dataclass(frozen=True)
class OcrPolicy:
    mode: OcrMode = OcrMode.AUTO
    language: str = "chi_sim+eng"
    minimum_native_characters: int = 10
    allow_cloud: bool = False

    def needs_ocr(self, native_text: str) -> bool:
        if self.mode == OcrMode.NEVER:
            return False
        if self.mode == OcrMode.ALWAYS:
            return True
        return len("".join(native_text.split())) < self.minimum_native_characters
