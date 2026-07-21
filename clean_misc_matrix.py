from pathlib import Path

from pipeline.cleaners.energy_cleaner import clean_energy_text

# ============================================================
# INPUT FILES
# ============================================================

BASE_DIR = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\cleaned\MATRIX Files -20260720T112301Z-1-001\MATRIX Files"
)

FILES = [
    BASE_DIR / "The Matrix book (ru).txt",
    BASE_DIR / "Дневник_ЭНЕРГИИ_ЛИНИИ_НЕБА_школа_Максима_Ульянова.txt",
    BASE_DIR / "Дневник-ДЕНЕЖНЫЕ ЭНЕРГИИ-школа Максима Ульянова.txt",
    BASE_DIR / "Дневник-ПРЕДНАЗНАЧЕНИЯ-школа Максима Ульянова.txt",
    BASE_DIR / "Дневник-РОДОВЫЕ ЛИНИИ-школа Максима Ульянова.txt",
    BASE_DIR / "Дневник-ЭНЕРГИИ ЛИНИИ ЗЕМЛИ-школа Максима Ульянова.txt",
    BASE_DIR / "Дневник-ЭНЕРГИИ ЛИЧНОГО КВАДРАТА-школа Максима Ульянова.txt",
    BASE_DIR / "Point Values (ru).txt",
]

OUTPUT_DIR = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\misc_cleaned"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================


def process_file(file_path: Path):

    if not file_path.exists():
        print(f"⚠ File not found: {file_path.name}")
        return False

    text = file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    cleaned = clean_energy_text(text)

    output_path = OUTPUT_DIR / file_path.name

    output_path.write_text(
        cleaned,
        encoding="utf-8"
    )

    print(f"✓ {file_path.name}")

    return True


def main():

    success = 0
    failed = 0

    print("=" * 70)
    print(f"Processing {len(FILES)} files")
    print("=" * 70)

    for i, file in enumerate(FILES, start=1):

        print(f"[{i}/{len(FILES)}] {file.name}")

        try:

            if process_file(file):
                success += 1
            else:
                failed += 1

        except Exception as e:

            failed += 1

            print(f"✗ Error processing: {file.name}")
            print(e)

    print()
    print("=" * 70)
    print("MISC MATRIX CLEANING COMPLETE")
    print("=" * 70)
    print(f"Total Files : {len(FILES)}")
    print(f"Successful : {success}")
    print(f"Failed     : {failed}")
    print(f"Output     : {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()