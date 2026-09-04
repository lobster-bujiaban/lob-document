from __future__ import annotations

import hashlib
import re

from lob_document.domain import Block, BlockType, DocumentNode, DocumentTree, SourceDocument


_CJK_END = re.compile(r"[\u3400-\u9fff，。；：！？、）》】]$")
_CJK_START = re.compile(r"^[\u3400-\u9fff（《【]")


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    result = lines[0]
    for line in lines[1:]:
        separator = "" if _CJK_END.search(result) or _CJK_START.search(line) else " "
        result += separator + line
    return result


def _max_font_size(block: Block) -> float:
    return max((span.font_size or 0 for span in block.spans), default=0)


def _node_id(document_id: str, block_ids: list[str]) -> str:
    digest = hashlib.sha256(":".join(block_ids).encode()).hexdigest()[:16]
    return f"{document_id}_node_{digest}"


def build_document_tree(document: SourceDocument) -> SourceDocument:
    """Build a traceable semantic tree while excluding page furniture."""
    content = [
        block
        for page in document.pages
        for block in sorted(page.blocks, key=lambda item: item.reading_order)
        if block.type not in {BlockType.HEADER, BlockType.FOOTER}
    ]
    heading_sizes = sorted({_max_font_size(block) for block in content if block.type == BlockType.HEADING}, reverse=True)
    largest_heading = heading_sizes[0] if heading_sizes else 0

    roots: list[DocumentNode] = []
    section: DocumentNode | None = None
    subsection: DocumentNode | None = None
    for block in content:
        text = _normalize_text(block.text or "")
        if not text and block.figure is None and block.table is None:
            continue
        level = None
        if block.type == BlockType.HEADING:
            level = block.heading_level or (1 if _max_font_size(block) == largest_heading else 2)
        node = DocumentNode(
            id=_node_id(document.source.id, [block.id]),
            type=block.type,
            text=text,
            heading_level=level,
            source_block_ids=[block.id],
            source_refs=[block.source_ref],
            table=block.table,
            figure=block.figure,
        )
        if level == 1:
            roots.append(node)
            section = node
            subsection = None
        elif level == 2 and section is not None:
            section.children.append(node)
            subsection = node
        elif subsection is not None:
            subsection.children.append(node)
        elif section is not None:
            section.children.append(node)
        else:
            roots.append(node)

    title = document.metadata.get("Title") or document.source.filename.rsplit(".", 1)[0]
    tree = DocumentTree(id=f"{document.source.id}_tree", title=title, children=roots)
    return document.model_copy(update={"document_tree": tree})
