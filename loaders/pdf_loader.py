import fitz  # PyMuPDF


def extract_pdf_text(file_path: str) -> str:
    """
    Extract text from a PDF while preserving page order.
    """

    document = fitz.open(file_path)

    pages = []

    for page in document:
        text = page.get_text("text")
        pages.append(text)

    document.close()

    return "\n".join(pages)