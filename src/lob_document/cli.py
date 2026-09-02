from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lob-document",
        description="Traceable document parsing for AI and RAG",
    )
    parser.add_argument("source", nargs="?", help="document path to parse")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.source is None:
        parser.print_help()
        return
    parser.error("document parsing will be implemented in stage 1")


if __name__ == "__main__":
    main()
