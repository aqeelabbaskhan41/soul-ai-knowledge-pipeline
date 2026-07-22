from pathlib import Path
import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

# =====================================================
# CONFIGURATION
# =====================================================

load_dotenv()

INPUT_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\chunks"
)

OUTPUT_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\embedded_chunks"
)

EMBEDDING_MODEL = "text-embedding-3-small"
EXPECTED_DIM = 1536
BATCH_SIZE = 64
MAX_RETRIES = 5

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)


# =====================================================
# HELPERS
# =====================================================

def already_embedded(output_file: Path) -> bool:
    """Skip files that already have complete embeddings."""
    if not output_file.exists():
        return False

    try:
        with open(output_file, encoding="utf-8") as f:
            chunks = json.load(f)

        if not isinstance(chunks, list) or len(chunks) == 0:
            return False

        return all(
            isinstance(c.get("embedding"), list)
            and len(c["embedding"]) == EXPECTED_DIM
            for c in chunks
        )
    except (json.JSONDecodeError, OSError, TypeError):
        return False


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API with retries."""
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )

            # Sort by index to keep order stable
            data = sorted(response.data, key=lambda item: item.index)
            vectors = [item.embedding for item in data]

            for vector in vectors:
                if len(vector) != EXPECTED_DIM:
                    raise ValueError(
                        f"Expected {EXPECTED_DIM} dims, got {len(vector)}"
                    )

            return vectors

        except RateLimitError as e:
            last_error = e
            wait = min(2 ** attempt, 60)
            print(f"   Rate limit — retry {attempt}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)

        except APIError as e:
            last_error = e
            wait = min(2 ** attempt, 30)
            print(f"   API error — retry {attempt}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {last_error}")


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Add embeddings to every chunk, in batches."""
    texts = [chunk["content"] for chunk in chunks]
    all_embeddings = []

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        vectors = get_embeddings(batch)
        all_embeddings.extend(vectors)

        done = min(start + BATCH_SIZE, len(texts))
        print(f"   Embedded {done}/{len(texts)}")

    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding

    return chunks


def process_file(file_path: Path) -> int:
    output_file = OUTPUT_FOLDER / file_path.name

    print(f"\nProcessing: {file_path.name}")

    if already_embedded(output_file):
        print("   Skipped (already embedded)")
        with open(output_file, encoding="utf-8") as f:
            return len(json.load(f))

    with open(file_path, encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        print("   Skipped (empty)")
        return 0

    embedded = embed_chunks(chunks)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            embedded,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"   Chunks : {len(embedded)}")
    print(f"   Dims   : {len(embedded[0]['embedding'])}")
    print(f"   Output : {output_file.name}")

    return len(embedded)


# =====================================================
# MAIN
# =====================================================

def main():
    files = sorted(INPUT_FOLDER.glob("*.json"))

    print("=" * 60)
    print("Embedding Generator")
    print("=" * 60)
    print(f"Model      : {EMBEDDING_MODEL}")
    print(f"Dimension  : {EXPECTED_DIM}")
    print(f"Files      : {len(files)}")
    print(f"Input      : {INPUT_FOLDER}")
    print(f"Output     : {OUTPUT_FOLDER}")

    total_chunks = 0
    processed = 0
    skipped = 0
    errors = 0

    for file in files:
        try:
            count = process_file(file)
            total_chunks += count
            processed += 1
        except Exception as e:
            errors += 1
            print(f"\nERROR : {file.name}")
            print(f"Reason: {e}")
            continue

        # Light pause between files to reduce rate-limit pressure
        time.sleep(0.2)

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Files processed : {processed}")
    print(f"Files with error: {errors}")
    print(f"Total chunks    : {total_chunks}")
    print(f"Output          : {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()
