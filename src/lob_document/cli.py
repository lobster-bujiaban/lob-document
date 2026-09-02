from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from lob_document.domain import SourceDocument
from lob_document.exporters import export_markdown
from lob_document.layout import build_document_tree
from lob_document.loaders import load_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lob-document",
        description="Traceable document parsing for AI and RAG",
    )
    subparsers = parser.add_subparsers(dest="command")
    parse_parser = subparsers.add_parser("parse", help="extract native PDF text and structure")
    parse_parser.add_argument("source", type=Path, help="PDF path to parse")
    parse_parser.add_argument("--output", "-o", type=Path, help="output JSON path (stdout by default)")
    parse_parser.add_argument("--markdown", type=Path, help="write traceable Markdown output")
    schema_parser = subparsers.add_parser("schema", help="print the SourceDocument JSON Schema")
    schema_parser.add_argument("--output", "-o", type=Path, help="output schema path (stdout by default)")
    return parser


def _write_json(payload: dict[str, object], output: Path | None) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(content)
        return
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _write_text(content: str, output: Path) -> None:
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    try:
        if args.command == "schema":
            _write_json(SourceDocument.model_json_schema(), args.output)
            return
        document = build_document_tree(load_pdf(args.source))
        _write_json(document.model_dump(mode="json"), args.output)
        if args.markdown is not None:
            _write_text(export_markdown(document), args.markdown)
    except (FileNotFoundError, ValueError, OSError, ValidationError) as exc:
        parser.exit(2, f"lob-document: error: {exc}\n")


if __name__ == "__main__":
    main()
