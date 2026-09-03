"""Unified domain model for document parsing."""

from .models import (
    Block,
    BlockType,
    BoundingBox,
    CoordinateSystem,
    Diagnostic,
    DiagnosticSeverity,
    DocumentNode,
    DocumentTree,
    FileIdentity,
    Page,
    SourceDocument,
    SourceMethod,
    SourceRef,
    TableCell,
    TableData,
    TextSpan,
)

__all__ = [
    "Block",
    "BlockType",
    "BoundingBox",
    "CoordinateSystem",
    "Diagnostic",
    "DiagnosticSeverity",
    "DocumentNode",
    "DocumentTree",
    "FileIdentity",
    "Page",
    "SourceDocument",
    "SourceMethod",
    "SourceRef",
    "TableCell",
    "TableData",
    "TextSpan",
]
