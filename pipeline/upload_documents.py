"""
Safe document upload to Supabase `documents` table.

Usage:
  # Preview only (no DB writes)
  python pipeline/upload_documents.py --dry-run

  # Insert ONE file for verification
  python pipeline/upload_documents.py --test-one "01 ENERGY (ru).json" --execute

  # Insert all documents
  python pipeline/upload_documents.py --execute
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

KNOWLEDGE_BASE = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\knowledge_base"
)

MAP_FILE_DEV = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\pipeline\document_id_map.json"
)
MAP_FILE_PROD = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\pipeline\document_id_map_prod.json"
)

EXPECTED_DIM = 1536
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
        # Prefer service role for inserts (RLS bypass). Fall back to SUPABASE_KEY.
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
        )
        missing = "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY"

    if not url or not key:
        raise RuntimeError(f"Missing {missing}")

    return create_client(url, key), key


def key_looks_like_service_role(key: str) -> bool:
    # JWT payload is base64; role claim is the reliable signal when present
    try:
        import base64

        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return data.get("role") == "service_role"
    except Exception:
        return "service_role" in key


def find_source_txt(filename: str) -> Path | None:
    """Locate original cleaned TXT under knowledge_base."""
    matches = list(KNOWLEDGE_BASE.rglob(filename))
    return matches[0] if matches else None


def load_map() -> dict:
    if MAP_FILE.exists():
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    return {}


def save_map(mapping: dict) -> None:
    MAP_FILE.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_embedded_file(path: Path) -> list[dict]:
    chunks = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(chunks, list) or len(chunks) == 0:
        raise ValueError(f"{path.name}: empty or invalid JSON array")

    for i, chunk in enumerate(chunks):
        for field in ("chunk_index", "content", "token_count", "embedding", "metadata"):
            if field not in chunk:
                raise ValueError(f"{path.name}[{i}]: missing '{field}'")

        emb = chunk["embedding"]
        if not isinstance(emb, list) or len(emb) != EXPECTED_DIM:
            raise ValueError(
                f"{path.name}[{i}]: embedding dim {len(emb) if isinstance(emb, list) else type(emb)} != {EXPECTED_DIM}"
            )

    return chunks


def build_document_payload(json_path: Path, chunks: list[dict]) -> dict:
    meta_filename = chunks[0]["metadata"].get("filename")
    if not meta_filename:
        raise ValueError(f"{json_path.name}: metadata.filename missing")

    source = find_source_txt(meta_filename)
    file_size = source.stat().st_size if source else None
    text_len = source.read_text(encoding="utf-8", errors="ignore").__len__() if source else None

    return {
        "filename": meta_filename,
        "content_type": "text/plain",
        "file_size": file_size,
        "total_chunks": len(chunks),
        "language": "ru",
        "metadata": {
            "original_text_length": text_len,
            "chunk_json": json_path.name,
            "pipeline_version": "v1",
        },
    }


def find_existing_document(sb, filename: str) -> dict | None:
    result = (
        sb.table("documents")
        .select("id,filename,total_chunks,language,content_type")
        .eq("filename", filename)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def process_one(sb, json_path: Path, execute: bool, mapping: dict) -> str | None:
    chunks = validate_embedded_file(json_path)
    payload = build_document_payload(json_path, chunks)

    print(f"\nFile: {json_path.name}")
    print(f"  filename     : {payload['filename']}")
    print(f"  content_type : {payload['content_type']}")
    print(f"  file_size    : {payload['file_size']}")
    print(f"  total_chunks : {payload['total_chunks']}")
    print(f"  language     : {payload['language']}")
    print(f"  metadata     : {payload['metadata']}")

    existing = find_existing_document(sb, payload["filename"])
    if existing:
        doc_id = existing["id"]
        print(f"  SKIP (already in DB) id={doc_id}")
        mapping[payload["filename"]] = {
            "document_id": doc_id,
            "json_file": json_path.name,
            "total_chunks": payload["total_chunks"],
        }
        return doc_id

    if not execute:
        print("  DRY-RUN: would INSERT into documents")
        return None

    result = sb.table("documents").insert(payload).execute()
    doc_id = result.data[0]["id"]
    print(f"  INSERTED id={doc_id}")

    mapping[payload["filename"]] = {
        "document_id": doc_id,
        "json_file": json_path.name,
        "total_chunks": payload["total_chunks"],
    }
    return doc_id


def main():
    parser = argparse.ArgumentParser(description="Upload documents to Supabase")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually insert rows (default is dry-run)",
    )
    parser.add_argument(
        "--test-one",
        type=str,
        default=None,
        help='Only process one JSON filename, e.g. "01 ENERGY (ru).json"',
    )
    parser.add_argument(
        "--force-anon",
        action="store_true",
        help="Allow insert attempt even if key is not service_role",
    )
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
    print("Upload Documents")
    print("=" * 60)
    print(f"Target      : {'PRODUCTION' if args.prod else 'DEV'}")
    print(f"Mode        : {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print(f"Key role    : {'service_role' if is_service else 'anon / unknown'}")
    print(f"Map file    : {MAP_FILE.name}")

    if args.execute and not is_service and not args.force_anon:
        print(
            "\nREFUSING EXECUTE: current key is not service_role.\n"
            "RLS will block inserts.\n"
            "Add SUPABASE_SERVICE_ROLE_KEY (or PROD equivalent) to .env, then re-run.\n"
            "(Use --force-anon only if you intentionally want to try anyway.)"
        )
        return

    files = sorted(EMBEDDED_FOLDER.glob("*.json"))
    if args.test_one:
        target = EMBEDDED_FOLDER / args.test_one
        if not target.exists():
            raise FileNotFoundError(target)
        files = [target]

    print(f"Files       : {len(files)}")

    mapping = load_map()
    inserted = 0
    errors = 0

    for path in files:
        try:
            process_one(sb, path, args.execute, mapping)
            inserted += 1
        except Exception as e:
            errors += 1
            print(f"\nERROR : {path.name}")
            print(f"Reason: {e}")

    if args.execute:
        save_map(mapping)
        print(f"\nSaved map   : {MAP_FILE}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"Processed : {inserted}")
    print(f"Errors    : {errors}")
    print(f"Mapped    : {len(mapping)}")


if __name__ == "__main__":
    main()
