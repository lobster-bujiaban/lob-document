from __future__ import annotations

from lob_document.domain import BlockType, DocumentNode, SourceDocument


def _source_comment(node: DocumentNode) -> str:
    refs = "; ".join(
        f"page={ref.page_number} bbox={ref.bbox.x0},{ref.bbox.y0},{ref.bbox.x1},{ref.bbox.y1}"
        for ref in node.source_refs
        if ref.bbox is not None
    )
    blocks = ",".join(node.source_block_ids)
    return f"<!-- source: {refs} blocks={blocks} -->"


def _render_node(node: DocumentNode, output: list[str]) -> None:
    output.append(_source_comment(node))
    if node.type == BlockType.HEADING:
        level = min(6, (node.heading_level or 2) + 1)
        output.append(f"{'#' * level} {node.text}")
    elif node.type == BlockType.LIST:
        output.append(f"- {node.text}")
    elif node.text:
        output.append(node.text)
    output.append("")
    for child in node.children:
        _render_node(child, output)


def export_markdown(document: SourceDocument) -> str:
    if document.document_tree is None:
        raise ValueError("document tree has not been built")
    output = [f"# {document.document_tree.title}", ""]
    for node in document.document_tree.children:
        _render_node(node, output)
    return "\n".join(output).rstrip() + "\n"
