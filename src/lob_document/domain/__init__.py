"""Unified domain model for document parsing."""

from .models import (
    Block,
    BlockType,
    BoundingBox,
    CoordinateSystem,
    Diagnostic,
    DiagnosticSeverity,
    FileIdentity,
    Page,
    SourceDocument,
    SourceMethod,
    SourceRef,
    TextSpan,
)

__all__ = [
    "Block",
    "BlockType",
    "BoundingBox",
    "CoordinateSystem",
    "Diagnostic",
    "DiagnosticSeverity",
    "FileIdentity",
    "Page",
    "SourceDocument",
    "SourceMethod",
    "SourceRef",
    "TextSpan",
]
