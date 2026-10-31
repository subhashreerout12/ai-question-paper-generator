"""PDF ingestion: extract text and split it into word-based chunks."""

import re

try:
    import pymupdf as fitz  # newer PyMuPDF versions
except ImportError:
    import fitz  # older PyMuPDF versions


def extract_text(pdf_path: str) -> str:
    """Return all text from the PDF as one cleaned string."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return re.sub(r"\s+", " ", "\n".join(pages)).strip()


def chunk_text(text: str, chunk_words: int = 1000) -> list[str]:
    """Split text into consecutive chunks of about chunk_words words."""
    words = text.split()
    return [
        " ".join(words[i : i + chunk_words])
        for i in range(0, len(words), chunk_words)
    ]
