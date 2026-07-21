import re


HEADER_PATTERN = re.compile(
    r"Матрица Изобилия\s*-\s*школа Максима Ульянова",
    re.IGNORECASE,
)

FOOTER_PATTERN = re.compile(
    r"ВЕРНУТЬСЯ К ОГЛАВЛЕНИЮ",
    re.IGNORECASE,
)

# Remove standalone domains or URLs
URL_PATTERN = re.compile(
    r"\(?[A-Za-z0-9.-]+\.[A-Za-z]{2,}\)?",
    re.IGNORECASE,
)

# Remove repeated page header like:
# ЭНЕРГИЯ 1 | + МАСТЕРСТВО... | - ...
ENERGY_HEADER_PATTERN = re.compile(
    r"^ЭНЕРГИЯ\s+\d+\s+\|.*$",
    re.IGNORECASE,
)


def clean_energy_text(text: str) -> str:
    """
    Cleaner for Matrix Energy documents.
    """

    lines = text.splitlines()
    cleaned = []

    for line in lines:

        line = HEADER_PATTERN.sub("", line)
        line = FOOTER_PATTERN.sub("", line)
        line = URL_PATTERN.sub("", line)

        line = line.strip()

        # Remove repeated energy page header
        if ENERGY_HEADER_PATTERN.match(line):
            continue

        # Remove standalone page numbers
        if re.fullmatch(r"\d{1,3}", line):
            continue

        cleaned.append(line)

    text = "\n".join(cleaned)

    # Normalize spaces
    text = re.sub(r"[ ]{2,}", " ", text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()