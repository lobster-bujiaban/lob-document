from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from lob_document.domain import FileIdentity, Page, SourceDocument


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pdf_baseline(path: Path) -> SourceDocument:
    """Load stable PDF identity and page geometry without extracting content."""
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
    for index, pdf_page in enumerate(reader.pages, start=1):
        box = pdf_page.mediabox
        pages.append(
            Page(
                id=f"{document_id}_page_{index:04d}",
                page_number=index,
                width=float(box.width),
                height=float(box.height),
                rotation=int(pdf_page.rotation or 0) % 360,
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
