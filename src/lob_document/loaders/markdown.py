from __future__ import annotations

import hashlib
import re
from pathlib import Path

from lob_document.domain import Block, BlockType, BoundingBox, FileIdentity, Page, SourceDocument, SourceMethod, SourceRef


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LIST = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$")


def load_markdown(path: Path) -> SourceDocument:
    source_path = path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"file does not exist: {source_path}")
    content = source_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    document_id = f"doc_{digest[:24]}"
    lines = content.splitlines()
    blocks: list[Block] = []
    index = 0
    order = 0
    while index < len(lines):
        if not lines[index].strip() or lines[index].lstrip().startswith("<!--"):
            index += 1
            continue
        start = index + 1
        line = lines[index].strip()
        heading = _HEADING.match(line)
        list_item = _LIST.match(line)
        block_type = BlockType.HEADING if heading else BlockType.LIST if list_item else BlockType.PARAGRAPH
        text_parts = [heading.group(2) if heading else list_item.group(1) if list_item else line]
        index += 1
        while index < len(lines) and lines[index].strip() and not _HEADING.match(lines[index].strip()) and not _LIST.match(lines[index].strip()):
            if not lines[index].lstrip().startswith("<!--"):
                text_parts.append(lines[index].strip())
            index += 1
        text = "\n".join(text_parts).strip()
        end = index
        bbox = BoundingBox(x0=0, y0=start - 1, x1=1, y1=max(start, end))
        ref = SourceRef(document_id=document_id, page_number=1, bbox=bbox, line_start=start, line_end=end)
        fingerprint = f"{start}:{end}:{text}".encode()
        blocks.append(
            Block(
                id=f"{document_id}_block_{hashlib.sha256(fingerprint).hexdigest()[:16]}",
                type=block_type,
                text=text,
                bbox=bbox,
                reading_order=order,
                source_method=SourceMethod.NATIVE,
                source_engine="markdown-loader",
                source_engine_version="1",
                confidence=1.0,
                source_ref=ref,
            )
        )
        order += 1
    page = Page(
        id=f"{document_id}_page_0001",
        page_number=1,
        width=1,
        height=max(1, len(lines)),
        blocks=blocks,
    )
    return SourceDocument(
        source=FileIdentity(
            id=document_id,
            sha256=digest,
            filename=source_path.name,
            media_type="text/markdown",
            size_bytes=source_path.stat().st_size,
        ),
        page_count=1,
        pages=[page],
    )
