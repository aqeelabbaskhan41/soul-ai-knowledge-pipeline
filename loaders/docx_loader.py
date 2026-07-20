from docx import Document


def extract_docx_text(file_path: str) -> str:
    """
    Extract text from a DOCX document.
    """

    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text)

    return "\n".join(paragraphs)