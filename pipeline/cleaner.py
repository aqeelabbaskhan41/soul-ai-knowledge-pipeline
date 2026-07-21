import re
import unicodedata


class TextCleaner:
    """
    Cleans extracted text while preserving its meaning.
    """

    @staticmethod
    def clean(text: str) -> str:
        # Normalize unicode characters
        text = unicodedata.normalize("NFKC", text)

        # Normalize line endings
        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Replace tabs with spaces
        text = text.replace("\t", " ")

        # Remove trailing spaces
        text = "\n".join(line.rstrip() for line in text.split("\n"))

        # Collapse multiple spaces
        text = re.sub(r"[ ]{2,}", " ", text)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text