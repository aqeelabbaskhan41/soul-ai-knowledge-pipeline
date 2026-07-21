from pathlib import Path
import json
import re

import tiktoken

# =====================================================
# CONFIGURATION
# =====================================================

INPUT_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\knowledge_base"
)

OUTPUT_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\chunks"
)

TARGET_TOKENS = 520
MAX_TOKENS = 600

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# OpenAI tokenizer (same family used for text-embedding-3-small)
encoding = tiktoken.encoding_for_model("text-embedding-3-small")


# =====================================================
# HELPERS
# =====================================================

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))


def split_large_paragraph(paragraph: str):
    """
    Split huge paragraphs into smaller sentence groups.
    """
    sentences = re.split(r'(?<=[.!?।])\s+', paragraph)

    groups = []
    current = ""

    for sentence in sentences:

        candidate = (
            current + " " + sentence
            if current
            else sentence
        )

        if count_tokens(candidate) <= MAX_TOKENS:
            current = candidate
        else:

            if current:
                groups.append(current.strip())

            current = sentence

    if current:
        groups.append(current.strip())

    return groups


def chunk_document(text: str):

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]

    if not paragraphs:
        return []

    chunks = []

    current_chunk = ""
    current_tokens = 0

    chunk_index = 0

    for paragraph in paragraphs:

        para_tokens = count_tokens(paragraph)

        # Huge paragraph
        if para_tokens > MAX_TOKENS:

            parts = split_large_paragraph(paragraph)

        else:

            parts = [paragraph]

        for part in parts:

            tokens = count_tokens(part)

            candidate = (
                current_chunk + "\n\n" + part
                if current_chunk
                else part
            )

            candidate_tokens = count_tokens(candidate)

            if candidate_tokens <= MAX_TOKENS:

                current_chunk = candidate
                current_tokens = candidate_tokens

            else:

                if current_chunk:

                    chunks.append({
                        "chunk_index": chunk_index,
                        "content": current_chunk.strip(),
                        "token_count": current_tokens,
                        "metadata": {}
                    })

                    chunk_index += 1

                current_chunk = part
                current_tokens = tokens

    if current_chunk:

        chunks.append({
            "chunk_index": chunk_index,
            "content": current_chunk.strip(),
            "token_count": current_tokens,
            "metadata": {}
        })

    return chunks


# =====================================================
# PROCESS FILE
# =====================================================

def process_file(file_path: Path):

    print(f"\nProcessing: {file_path.name}")

    text = file_path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    # Skip empty files
    if not text.strip():
        print("   Skipped (empty file)")
        return 0

    chunks = chunk_document(text)

    # Skip files that produced no chunks
    if len(chunks) == 0:
        print("   Skipped (no chunks generated)")
        return 0

    for chunk in chunks:
        chunk["metadata"] = {
            "filename": file_path.name
        }

    output_file = OUTPUT_FOLDER / f"{file_path.stem}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            chunks,
            f,
            ensure_ascii=False,
            indent=2
        )

    avg = round(
        sum(c["token_count"] for c in chunks) / len(chunks),
        1
    )

    minimum = min(c["token_count"] for c in chunks)
    maximum = max(c["token_count"] for c in chunks)

    print(f"   Chunks       : {len(chunks)}")
    print(f"   Avg Tokens   : {avg}")
    print(f"   Min Tokens   : {minimum}")
    print(f"   Max Tokens   : {maximum}")
    print(f"   Output       : {output_file.name}")

    return len(chunks)


# =====================================================
# MAIN
# =====================================================

def main():

    files = sorted(INPUT_FOLDER.rglob("*.txt"))

    print("=" * 60)
    print("Knowledge Base Chunking")
    print("=" * 60)

    print(f"Files Found : {len(files)}")

    total_chunks = 0

    for file in files:

        try:
            total_chunks += process_file(file)

        except Exception as e:
            print(f"\nERROR : {file.name}")
            print(f"Reason: {e}")
            continue

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

    print(f"Documents : {len(files)}")
    print(f"Chunks    : {total_chunks}")
    print(f"Output    : {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()