"""Document loaders."""

from .pdf import load_pdf
from .markdown import load_markdown
from .image import load_image
from .docx import load_docx

__all__ = ["load_docx", "load_image", "load_markdown", "load_pdf"]
