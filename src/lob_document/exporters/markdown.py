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


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def _render_table(node: DocumentNode) -> str:
    table = node.table
    if table is None:
        return node.text or ""
    if any(cell.row_span > 1 or cell.column_span > 1 for cell in table.cells):
        rows = ["<table>"]
        for row_index in range(table.row_count):
            rows.append("  <tr>")
            for cell in sorted((item for item in table.cells if item.row == row_index), key=lambda item: item.column):
                spans = ""
                if cell.row_span > 1:
                    spans += f' rowspan="{cell.row_span}"'
                if cell.column_span > 1:
                    spans += f' colspan="{cell.column_span}"'
                rows.append(f"    <td{spans}>{cell.text}</td>")
            rows.append("  </tr>")
        rows.append("</table>")
        return "\n".join(rows)
    matrix = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
    for cell in table.cells:
        if cell.row < table.row_count and cell.column < table.column_count:
            matrix[cell.row][cell.column] = _escape_cell(cell.text)
    lines = ["| " + " | ".join(row) + " |" for row in matrix]
    lines.insert(1, "| " + " | ".join("---" for _ in range(table.column_count)) + " |")
    return "\n".join(lines)


def _render_node(node: DocumentNode, output: list[str]) -> None:
    output.append(_source_comment(node))
    if node.type == BlockType.TABLE:
        output.append(_render_table(node))
    elif node.type == BlockType.HEADING:
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
