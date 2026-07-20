from pathlib import Path

from loaders.pdf_loader import extract_pdf_text
from loaders.docx_loader import extract_docx_text


DOCUMENTS_DIR = Path("documents")
OUTPUT_DIR = Path("output")

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_document(file_path: Path):
    """
    Extract text from a PDF or DOCX and save it as a .txt file
    while preserving the folder structure.
    """

    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        text = extract_pdf_text(str(file_path))

    elif suffix == ".docx":
        text = extract_docx_text(str(file_path))

    else:
        return False

    # Preserve folder structure
    relative_path = file_path.relative_to(DOCUMENTS_DIR)

    output_file = OUTPUT_DIR / relative_path.with_suffix(".txt")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_file.write_text(text, encoding="utf-8")

    print(f"✓ Extracted: {relative_path}")
    print(f"  Characters: {len(text):,}")
    print(f"  Output: {output_file}")
    print("-" * 60)

    return True


def main():

    files = [
        f
        for f in DOCUMENTS_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("No PDF or DOCX files found.")
        return

    print(f"\nFound {len(files)} document(s).\n")

    success = 0
    failed = 0

    for index, file in enumerate(files, start=1):

        print(f"[{index}/{len(files)}] Processing: {file.relative_to(DOCUMENTS_DIR)}")

        try:
            if extract_document(file):
                success += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1
            print(f"✗ Failed: {file}")
            print(e)
            print("-" * 60)

    print("\n========== EXTRACTION SUMMARY ==========")
    print(f"Total Files : {len(files)}")
    print(f"Successful : {success}")
    print(f"Failed      : {failed}")
    print("========================================")


if __name__ == "__main__":
    main()