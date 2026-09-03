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


class CoordinateSystem(StrEnum):
    PDF_POINTS_TOP_LEFT = "pdf_points_top_left"


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


class TextSpan(StrictModel):
    text: str
    bbox: BoundingBox
    font_name: str | None = None
    font_size: float | None = Field(default=None, gt=0)
    flags: int = Field(default=0, ge=0)


class TableCell(StrictModel):
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    text: str = ""
    bbox: BoundingBox
    confidence: float | None = Field(default=None, ge=0, le=1)


class TableData(StrictModel):
    row_count: int = Field(ge=1)
    column_count: int = Field(ge=1)
    cells: list[TableCell] = Field(default_factory=list)


class ImageAsset(StrictModel):
    id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FigureData(StrictModel):
    asset: ImageAsset
    caption: str | None = None


class Block(StrictModel):
    id: str
    type: BlockType
    text: str | None = None
    bbox: BoundingBox
    reading_order: int = Field(ge=0)
    source_method: SourceMethod
    source_engine: str | None = None
    source_engine_version: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_ref: SourceRef
    spans: list[TextSpan] = Field(default_factory=list)
    table: TableData | None = None
    figure: FigureData | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class Page(StrictModel):
    id: str
    page_number: int = Field(ge=1)
    width: float = Field(gt=0, description="Page width in PDF points")
    height: float = Field(gt=0, description="Page height in PDF points")
    rotation: int = Field(default=0, description="Clockwise rotation in degrees")
    coordinate_system: CoordinateSystem = CoordinateSystem.PDF_POINTS_TOP_LEFT
    blocks: list[Block] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class DocumentNode(StrictModel):
    id: str
    type: BlockType
    text: str | None = None
    heading_level: int | None = Field(default=None, ge=1, le=6)
    source_block_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    table: TableData | None = None
    figure: FigureData | None = None
    children: list[DocumentNode] = Field(default_factory=list)


class DocumentTree(StrictModel):
    id: str
    title: str
    children: list[DocumentNode] = Field(default_factory=list)


class SourceDocument(StrictModel):
    schema_version: str = "1.5"
    source: FileIdentity
    page_count: int = Field(ge=0)
    pages: list[Page] = Field(default_factory=list)
    document_tree: DocumentTree | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pages(self) -> SourceDocument:
        if self.page_count != len(self.pages):
            raise ValueError("page_count must equal the number of pages")
        return self
