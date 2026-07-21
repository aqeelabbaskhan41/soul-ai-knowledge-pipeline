from pathlib import Path

from pipeline.cleaners.energy_cleaner import clean_energy_text

# ============================================================
# CONFIGURATION
# ============================================================

INPUT_DIR = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\cleaned\MATRIX Files -20260720T112301Z-1-001\MATRIX Files\Childrens energy"
)

OUTPUT_DIR = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\children_energy_cleaned"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================


def process_file(file_path: Path):

    text = file_path.read_text(encoding="utf-8")

    cleaned = clean_energy_text(text)

    relative = file_path.relative_to(INPUT_DIR)

    output_path = OUTPUT_DIR / relative

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(cleaned, encoding="utf-8")

    print(f"✓ {relative}")


def main():

    files = sorted(INPUT_DIR.rglob("*.txt"))

    if not files:
        print("No txt files found.")
        return

    print("=" * 60)
    print(f"Found {len(files)} Children's Energy documents")
    print("=" * 60)

    success = 0
    failed = 0

    for index, file in enumerate(files, start=1):

        print(f"[{index}/{len(files)}] {file.name}")

        try:
            process_file(file)
            success += 1

        except Exception as e:
            failed += 1
            print(f"✗ {file.name}")
            print(e)

    print()
    print("=" * 60)
    print("CHILDREN'S ENERGY CLEANING COMPLETE")
    print("=" * 60)
    print(f"Processed : {len(files)}")
    print(f"Successful: {success}")
    print(f"Failed    : {failed}")
    print(f"Output    : {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()