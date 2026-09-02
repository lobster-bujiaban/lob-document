from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
from pypdf import PdfReader

from lob_document.domain import (
    Block,
    BlockType,
    BoundingBox,
    Diagnostic,
    DiagnosticSeverity,
    FileIdentity,
    Page,
    SourceDocument,
    SourceMethod,
    SourceRef,
    TextSpan,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: float) -> float:
    return round(max(0.0, float(value)), 4)


def _bbox(values: tuple[float, float, float, float] | list[float]) -> BoundingBox:
    return BoundingBox(x0=_number(values[0]), y0=_number(values[1]), x1=_number(values[2]), y1=_number(values[3]))


def _font_name(value: object) -> str | None:
    name = str(value) if value else None
    return "Type3" if name and name.startswith("Type3 (") else name


def _merge_spans(spans: list[TextSpan]) -> list[TextSpan]:
    merged: list[TextSpan] = []
    for span in spans:
        previous = merged[-1] if merged else None
        same_style = previous and (
            previous.font_name == span.font_name
            and previous.font_size == span.font_size
            and previous.flags == span.flags
        )
        same_line = previous and abs(previous.bbox.y0 - span.bbox.y0) <= max(previous.font_size or 1, 1) * 0.2
        adjacent = previous and 0 <= span.bbox.x0 - previous.bbox.x1 <= max(previous.font_size or 1, 1) * 0.35
        if same_style and same_line and adjacent:
            merged[-1] = previous.model_copy(
                update={
                    "text": previous.text + span.text,
                    "bbox": BoundingBox(
                        x0=previous.bbox.x0,
                        y0=min(previous.bbox.y0, span.bbox.y0),
                        x1=max(previous.bbox.x1, span.bbox.x1),
                        y1=max(previous.bbox.y1, span.bbox.y1),
                    ),
                }
            )
        else:
            merged.append(span)
    return merged


def _line_groups(raw_block: dict[str, object]) -> list[list[dict[str, object]]]:
    """Split engine blocks when lines are side-by-side or belong to different columns."""
    groups: list[list[dict[str, object]]] = []
    for line in raw_block.get("lines", []):  # type: ignore[union-attr]
        bbox = line["bbox"]
        if not groups:
            groups.append([line])
            continue
        previous = groups[-1][-1]
        previous_bbox = previous["bbox"]
        previous_height = max(1.0, previous_bbox[3] - previous_bbox[1])
        vertical_gap = bbox[1] - previous_bbox[3]
        same_row = abs(bbox[1] - previous_bbox[1]) <= previous_height * 0.5
        left_aligned = abs(bbox[0] - previous_bbox[0]) <= previous_height * 2
        overlaps_x = min(bbox[2], previous_bbox[2]) > max(bbox[0], previous_bbox[0])
        if not same_row and vertical_gap <= previous_height * 1.2 and (left_aligned or overlaps_x):
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def _reading_order(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """Order nearby rows left-to-right while keeping vertically separate content top-to-bottom."""
    pending = sorted(items, key=lambda item: (item["bbox"].y0, item["bbox"].x0))  # type: ignore[union-attr]
    ordered: list[dict[str, object]] = []
    while pending:
        first = pending.pop(0)
        first_bbox = first["bbox"]
        tolerance = max(3.0, (first_bbox.y1 - first_bbox.y0) * 0.35)  # type: ignore[union-attr]
        row = [first]
        rest = []
        for item in pending:
            bbox = item["bbox"]
            if abs(bbox.y0 - first_bbox.y0) <= tolerance:  # type: ignore[union-attr]
                row.append(item)
            else:
                rest.append(item)
        ordered.extend(sorted(row, key=lambda item: item["bbox"].x0))  # type: ignore[union-attr]
        pending = rest
    return ordered


def _extract_blocks(pdf_page: pymupdf.Page, document_id: str, page_number: int) -> list[Block]:
    candidates: list[dict[str, object]] = []
    raw = pdf_page.get_text("dict", sort=True)
    for raw_block in raw.get("blocks", []):
        if raw_block.get("type") != 0:
            continue
        for lines in _line_groups(raw_block):
            spans: list[TextSpan] = []
            line_texts: list[str] = []
            for line in lines:
                line_text: list[str] = []
                line_spans: list[TextSpan] = []
                for span in line.get("spans", []):
                    text = str(span.get("text", ""))
                    if not text:
                        continue
                    line_text.append(text)
                    line_spans.append(
                        TextSpan(
                            text=text,
                            bbox=_bbox(span["bbox"]),
                            font_name=_font_name(span.get("font")),
                            font_size=_number(span["size"]),
                            flags=max(0, int(span.get("flags", 0))),
                        )
                    )
                joined = "".join(line_text).strip()
                if joined:
                    line_texts.append(joined)
                    spans.extend(_merge_spans(line_spans))
            text = "\n".join(line_texts).strip()
            if not text or not spans:
                continue
            candidates.append(
                {
                    "text": text,
                    "bbox": BoundingBox(
                        x0=min(span.bbox.x0 for span in spans),
                        y0=min(span.bbox.y0 for span in spans),
                        x1=max(span.bbox.x1 for span in spans),
                        y1=max(span.bbox.y1 for span in spans),
                    ),
                    "spans": spans,
                }
            )

    ordered = _reading_order(candidates)
    font_sizes = [span.font_size for item in ordered for span in item["spans"] if span.font_size]  # type: ignore[union-attr]
    body_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 10.0
    extracted: list[Block] = []
    for reading_order, item in enumerate(ordered):
        text = item["text"]
        block_bbox = item["bbox"]
        spans = item["spans"]
        block_type = BlockType.PARAGRAPH
        if block_bbox.y1 <= pdf_page.rect.height * 0.065:
            block_type = BlockType.HEADER
        elif block_bbox.y0 >= pdf_page.rect.height * 0.94:
            block_type = BlockType.FOOTER
        elif len(text) <= 40:
            size_ratio = max(span.font_size or 0 for span in spans) / body_size
            if 1.3 <= size_ratio < 1.9 or size_ratio >= 3.0:
                block_type = BlockType.HEADING
        fingerprint = f"{page_number}:{block_bbox.model_dump_json()}:{text}".encode()
        block_id = f"{document_id}_block_{hashlib.sha256(fingerprint).hexdigest()[:16]}"
        source_ref = SourceRef(document_id=document_id, page_number=page_number, bbox=block_bbox)
        extracted.append(
            Block(
                id=block_id,
                type=block_type,
                text=text,
                bbox=block_bbox,
                reading_order=reading_order,
                source_method=SourceMethod.NATIVE,
                confidence=1.0,
                source_ref=source_ref,
                spans=spans,
            )
        )
    return extracted


def load_pdf(path: Path) -> SourceDocument:
    """Load PDF identity, page geometry, and native text blocks."""
    source_path = path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"file does not exist: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"only PDF input is supported in stage 0: {source_path}")

    sha256 = _sha256(source_path)
    document_id = f"doc_{sha256[:24]}"
    reader = PdfReader(source_path, strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("encrypted PDF cannot be opened without a password") from exc

    pages = []
    with pymupdf.open(source_path) as native_pdf:
        for index, native_page in enumerate(native_pdf, start=1):
            blocks = _extract_blocks(native_page, document_id, index)
            source_ref = SourceRef(document_id=document_id, page_number=index)
            diagnostics = []
            if not blocks:
                diagnostics.append(
                    Diagnostic(
                        code="no_native_text",
                        severity=DiagnosticSeverity.WARNING,
                        message="No native text layer found; this page may require OCR.",
                        source_ref=source_ref,
                    )
                )
            pages.append(
                Page(
                    id=f"{document_id}_page_{index:04d}",
                    page_number=index,
                    width=_number(native_page.rect.width),
                    height=_number(native_page.rect.height),
                    rotation=int(native_page.rotation or 0) % 360,
                    blocks=blocks,
                    diagnostics=diagnostics,
                )
            )

    metadata = {
        str(key).removeprefix("/"): str(value)
        for key, value in (reader.metadata or {}).items()
        if value is not None
    }
    return SourceDocument(
        source=FileIdentity(
            id=document_id,
            sha256=sha256,
            filename=source_path.name,
            media_type="application/pdf",
            size_bytes=source_path.stat().st_size,
        ),
        page_count=len(pages),
        pages=pages,
        metadata=metadata,
    )
