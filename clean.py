from pathlib import Path

from pipeline.cleaner import TextCleaner


INPUT_DIR = Path("output")
OUTPUT_DIR = Path("cleaned")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_file(file_path: Path):

    text = file_path.read_text(encoding="utf-8")

    cleaned = TextCleaner.clean(text)

    relative = file_path.relative_to(INPUT_DIR)

    output_path = OUTPUT_DIR / relative

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(cleaned, encoding="utf-8")

    print(f"✓ {relative}")


def main():

    files = list(INPUT_DIR.rglob("*.txt"))

    print(f"Found {len(files)} text files.\n")

    success = 0

    for file in files:
        try:
            clean_file(file)
            success += 1

        except Exception as e:
            print(file)
            print(e)

    print("\nFinished")
    print(f"Cleaned {success} files")


if __name__ == "__main__":
    main()