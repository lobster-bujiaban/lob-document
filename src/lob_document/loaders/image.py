from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pymupdf

from lob_document.domain import Block, BlockType, BoundingBox, FigureData, FileIdentity, ImageAsset, Page, SourceDocument, SourceMethod, SourceRef
from lob_document.ocr import OcrEngine, OcrMode, OcrPolicy, TesseractOcrEngine
from lob_document.loaders.pdf import _ocr_blocks, _ocr_table_blocks


def load_image(
    path: Path,
    ocr_policy: OcrPolicy | None = None,
    ocr_engine: OcrEngine | None = None,
    artifacts_dir: Path | None = None,
) -> SourceDocument:
    source_path = path.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"file does not exist: {source_path}")
    if source_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("supported image formats are PNG, JPG, JPEG and WEBP")
    data = source_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    document_id = f"doc_{digest[:24]}"
    policy = ocr_policy or OcrPolicy()
    engine = ocr_engine or TesseractOcrEngine()
    if engine.is_cloud and not policy.allow_cloud:
        raise ValueError("cloud OCR is disabled for this document; explicitly allow cloud processing")

    with pymupdf.open(source_path) as image_document:
        image_page = image_document[0]
        width, height = image_page.rect.width, image_page.rect.height
        asset_name = f"asset_{digest[:24]}{source_path.suffix.lower()}"
        asset_path = Path("assets") / asset_name
        if artifacts_dir is not None:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, artifacts_dir / asset_name)
        else:
            asset_path = source_path
        page_bbox = BoundingBox(x0=0, y0=0, x1=round(width, 4), y1=round(height, 4))
        source_ref = SourceRef(document_id=document_id, page_number=1, bbox=page_bbox)
        figure = Block(
            id=f"{document_id}_figure_{digest[:16]}",
            type=BlockType.FIGURE,
            bbox=page_bbox,
            reading_order=0,
            source_method=SourceMethod.NATIVE,
            source_engine="image-loader",
            source_engine_version="1",
            source_ref=source_ref,
            figure=FigureData(asset=ImageAsset(
                id=f"asset_{digest[:24]}",
                path=str(asset_path),
                sha256=digest,
                media_type=f"image/{source_path.suffix.lower().lstrip('.')}",
                width=int(width),
                height=int(height),
            )),
        )
        blocks = [figure]
        diagnostics = []
        if policy.mode != OcrMode.NEVER:
            try:
                result = engine.recognize(image_page, policy.language)
                blocks.extend(_ocr_blocks(result, document_id, 1))
                blocks.extend(_ocr_table_blocks(result, document_id, 1))
                blocks = [block.model_copy(update={"reading_order": index}) for index, block in enumerate(sorted(blocks, key=lambda item: (item.bbox.y0, item.bbox.x0)))]
                diagnostics.append({"code": "ocr_applied", "severity": "info", "message": f"OCR applied with {result.engine}; extracted {len(result.lines)} text lines.", "source_ref": source_ref})
            except RuntimeError as exc:
                diagnostics.append({"code": "cloud_ocr_failed" if engine.is_cloud else "ocr_unavailable", "severity": "error", "message": str(exc), "source_ref": source_ref})
        page = Page(id=f"{document_id}_page_0001", page_number=1, width=width, height=height, blocks=blocks, diagnostics=diagnostics)
    return SourceDocument(
        source=FileIdentity(id=document_id, sha256=digest, filename=source_path.name, media_type=f"image/{source_path.suffix.lower().lstrip('.')}", size_bytes=len(data)),
        page_count=1,
        pages=[page],
    )
