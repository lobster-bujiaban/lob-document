from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceMethod(StrEnum):
    NATIVE = "native"
    OCR = "ocr"
    DERIVED = "derived"


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    FORMULA = "formula"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class FileIdentity(StrictModel):
    id: str = Field(description="Stable content-derived document ID")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    filename: str
    media_type: str
    size_bytes: int = Field(ge=0)


class BoundingBox(StrictModel):
    x0: float = Field(ge=0)
    y0: float = Field(ge=0)
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_extents(self) -> BoundingBox:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("bounding box end must not precede its start")
        return self


class SourceRef(StrictModel):
    document_id: str
    page_number: int = Field(ge=1)
    bbox: BoundingBox | None = None


class Diagnostic(StrictModel):
    code: str
    severity: DiagnosticSeverity
    message: str
    source_ref: SourceRef | None = None


class Block(StrictModel):
    id: str
    type: BlockType
    text: str | None = None
    bbox: BoundingBox
    reading_order: int = Field(ge=0)
    source_method: SourceMethod
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_ref: SourceRef
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class Page(StrictModel):
    id: str
    page_number: int = Field(ge=1)
    width: float = Field(gt=0, description="Page width in PDF points")
    height: float = Field(gt=0, description="Page height in PDF points")
    rotation: int = Field(default=0, description="Clockwise rotation in degrees")
    blocks: list[Block] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class SourceDocument(StrictModel):
    schema_version: str = "1.0"
    source: FileIdentity
    page_count: int = Field(ge=0)
    pages: list[Page] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pages(self) -> SourceDocument:
        if self.page_count != len(self.pages):
            raise ValueError("page_count must equal the number of pages")
        return self
