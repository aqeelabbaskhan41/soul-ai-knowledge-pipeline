"""
Safe chunk upload to Supabase `document_chunks` table.

Requires document_id_map.json from upload_documents.py.

Usage:
  # Preview only
  python pipeline/upload_chunks.py --dry-run

  # Upload chunks for ONE document (after documents are inserted)
  python pipeline/upload_chunks.py --test-one "01 ENERGY (ru).json" --execute

  # Upload all chunks
  python pipeline/upload_chunks.py --execute
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# =====================================================
# CONFIGURATION
# =====================================================

load_dotenv(override=True)

EMBEDDED_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\embedded_chunks"
)

MAP_FILE_DEV = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\pipeline\document_id_map.json"
)
MAP_FILE_PROD = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\pipeline\document_id_map_prod.json"
)

EXPECTED_DIM = 1536
BATCH_SIZE = 20  # keep batches small for vector payloads
USE_PROD = False
MAP_FILE = MAP_FILE_DEV


def configure_target(prod: bool) -> None:
    global USE_PROD, MAP_FILE
    USE_PROD = prod
    MAP_FILE = MAP_FILE_PROD if prod else MAP_FILE_DEV


def get_supabase():
    if USE_PROD:
        url = os.getenv("SUPABASE_PROD_URL")
        key = (
            os.getenv("SUPABASE_PROD_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_PROD_KEY")
        )
        missing = "SUPABASE_PROD_URL / SUPABASE_PROD_SERVICE_ROLE_KEY"
    else:
        url = os.getenv("SUPABASE_URL")
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
        )
        missing = "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY"

    if not url or not key:
        raise RuntimeError(f"Missing {missing}")
    return create_client(url, key), key


def key_looks_like_service_role(key: str) -> bool:
    try:
        import base64

        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return data.get("role") == "service_role"
    except Exception:
        return "service_role" in key


def load_map() -> dict:
    if not MAP_FILE.exists():
        raise FileNotFoundError(
            f"Missing {MAP_FILE}. Run upload_documents.py --execute first."
        )
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def validate_chunk(chunk: dict, filename: str, total_chunks: int) -> dict:
    for field in ("chunk_index", "content", "token_count", "embedding"):
        if field not in chunk:
            raise ValueError(f"missing field '{field}'")

    emb = chunk["embedding"]
    if not isinstance(emb, list) or len(emb) != EXPECTED_DIM:
        raise ValueError(
            f"bad embedding dim: {len(emb) if isinstance(emb, list) else type(emb)}"
        )

    metadata = dict(chunk.get("metadata") or {})
    metadata.setdefault("filename", filename)
    metadata["chunk_of"] = total_chunks

    return {
        "chunk_index": chunk["chunk_index"],
        "content": chunk["content"],
        "embedding": emb,
        "token_count": chunk["token_count"],
        "metadata": metadata,
        "summary": chunk.get("summary"),  # None for now — Phase 8
    }


def existing_chunk_indexes(sb, document_id: str) -> set[int]:
    result = (
        sb.table("document_chunks")
        .select("chunk_index")
        .eq("document_id", document_id)
        .execute()
    )
    return {row["chunk_index"] for row in result.data}


def process_one(
    sb,
    json_path: Path,
    document_id: str,
    execute: bool,
) -> tuple[int, int]:
    chunks = json.loads(json_path.read_text(encoding="utf-8"))
    filename = chunks[0]["metadata"]["filename"]
    total = len(chunks)

    print(f"\nFile: {json_path.name}")
    print(f"  document_id  : {document_id}")
    print(f"  filename     : {filename}")
    print(f"  total_chunks : {total}")

    already = existing_chunk_indexes(sb, document_id)
    print(f"  already in DB: {len(already)}")

    to_insert = []
    for chunk in chunks:
        payload = validate_chunk(chunk, filename, total)
        if payload["chunk_index"] in already:
            continue
        row = {
            "document_id": document_id,
            **payload,
        }
        to_insert.append(row)

    print(f"  to insert    : {len(to_insert)}")

    if not to_insert:
        print("  SKIP (all chunks already present)")
        return 0, total

    # Show first payload shape without dumping embedding
    sample = {k: v for k, v in to_insert[0].items() if k != "embedding"}
    sample["embedding"] = f"[{EXPECTED_DIM} floats]"
    print(f"  sample row   : {sample}")

    if not execute:
        print("  DRY-RUN: would INSERT document_chunks in batches")
        return 0, total

    inserted = 0
    for start in range(0, len(to_insert), BATCH_SIZE):
        batch = to_insert[start:start + BATCH_SIZE]
        sb.table("document_chunks").insert(batch).execute()
        inserted += len(batch)
        print(f"  inserted {inserted}/{len(to_insert)}")

    return inserted, total


def main():
    parser = argparse.ArgumentParser(description="Upload chunks to Supabase")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--test-one",
        type=str,
        default=None,
        help='Only one JSON file, e.g. "01 ENERGY (ru).json"',
    )
    parser.add_argument("--force-anon", action="store_true")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Target production Supabase (SUPABASE_PROD_*)",
    )
    args = parser.parse_args()

    configure_target(args.prod)
    sb, key = get_supabase()
    is_service = key_looks_like_service_role(key)

    print("=" * 60)
    print("Upload Chunks")
    print("=" * 60)
    print(f"Target   : {'PRODUCTION' if args.prod else 'DEV'}")
    print(f"Mode     : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"Key role : {'service_role' if is_service else 'anon / unknown'}")
    print(f"Map file : {MAP_FILE.name}")

    if args.execute and not is_service and not args.force_anon:
        print(
            "\nREFUSING EXECUTE: current key is not service_role.\n"
            "Add SUPABASE_SERVICE_ROLE_KEY (or PROD equivalent) to .env, then re-run."
        )
        return

    mapping = load_map()

    # Build reverse lookup: json_file -> document_id
    by_json = {
        info["json_file"]: info
        for info in mapping.values()
    }

    files = sorted(EMBEDDED_FOLDER.glob("*.json"))
    if args.test_one:
        files = [EMBEDDED_FOLDER / args.test_one]
        if not files[0].exists():
            raise FileNotFoundError(files[0])

    total_inserted = 0
    errors = 0

    for path in files:
        info = by_json.get(path.name)
        if not info:
            print(f"\nSKIP (no document_id map): {path.name}")
            continue
        try:
            inserted, _ = process_one(
                sb,
                path,
                info["document_id"],
                args.execute,
            )
            total_inserted += inserted
        except Exception as e:
            errors += 1
            print(f"\nERROR : {path.name}")
            print(f"Reason: {e}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Chunks inserted : {total_inserted}")
    print(f"Errors          : {errors}")


if __name__ == "__main__":
    main()