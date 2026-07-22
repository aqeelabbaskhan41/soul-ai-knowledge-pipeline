"""
Generate short Russian summaries for each chunk.

Phase A (local, reliable):
  Read embedded_chunks/*.json
  Call OpenAI
  Write summary back into the same JSON files

Phase B (Supabase sync):
  Push local summaries into document_chunks.summary

Usage:
  python pipeline/generate_chunk_summaries.py --local --execute
  python pipeline/generate_chunk_summaries.py --local --test-one "01 ENERGY (ru).json" --execute
  python pipeline/generate_chunk_summaries.py --sync --execute
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError as OpenAIAPIError
from supabase import create_client, Client

load_dotenv(override=True)

EMBEDDED_FOLDER = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\embedded_chunks"
)
MAP_FILE = Path(
    r"F:\FaisalBhaiWork\knowledge_ingestion\pipeline\document_id_map.json"
)

CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_RETRIES = 8
SLEEP_BETWEEN = 0.05
LOCAL_WORKERS = 8
SYNC_BATCH = 25

SYSTEM_PROMPT = (
    "Ты помощник для базы знаний Матрицы Судьбы. "
    "Напиши краткое содержание фрагмента текста на русском языке. "
    "Ровно 1 предложение, 20–35 слов. "
    "Без кавычек, без маркированных списков, без вступлений."
)


def make_openai() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=key)


def make_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing Supabase credentials")
    return create_client(url, key)


def generate_summary(client: OpenAI, content: str) -> str:
    text = content.strip()
    if len(text) > 6000:
        text = text[:6000]

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                temperature=0.2,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            summary = (response.choices[0].message.content or "").strip()
            summary = " ".join(summary.split())
            if not summary:
                raise ValueError("Empty summary")
            return summary
        except RateLimitError as e:
            last_error = e
            time.sleep(min(2 ** attempt, 60))
        except OpenAIAPIError as e:
            last_error = e
            time.sleep(min(2 ** attempt, 30))

    raise RuntimeError(f"OpenAI failed: {last_error}")


# =====================================================
# LOCAL GENERATION
# =====================================================

def process_local_file(client: OpenAI, path: Path, execute: bool) -> tuple[int, int]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    missing_indexes = [
        i for i, c in enumerate(chunks)
        if not (isinstance(c.get("summary"), str) and c["summary"].strip())
    ]

    print(f"\nFile: {path.name}")
    print(f"  chunks : {len(chunks)}")
    print(f"  need   : {len(missing_indexes)}")

    if not missing_indexes:
        print("  SKIP (already summarized locally)")
        return 0, 0

    if not execute:
        print("  DRY-RUN")
        return 0, len(missing_indexes)

    done = 0
    errors = 0

    def work(i: int) -> tuple[int, str]:
        summary = generate_summary(client, chunks[i]["content"])
        return i, summary

    with ThreadPoolExecutor(max_workers=LOCAL_WORKERS) as pool:
        futures = {pool.submit(work, i): i for i in missing_indexes}
        for future in as_completed(futures):
            i = futures[future]
            try:
                idx, summary = future.result()
                chunks[idx]["summary"] = summary
                done += 1
                if done == 1 or done % 20 == 0 or done == len(missing_indexes):
                    print(
                        f"  {done}/{len(missing_indexes)}  "
                        f"idx {chunks[idx]['chunk_index']}: {summary[:90]}..."
                    )
                if done % 10 == 0:
                    path.write_text(
                        json.dumps(chunks, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                time.sleep(SLEEP_BETWEEN)
            except Exception as e:
                errors += 1
                print(f"  ERROR idx {chunks[i].get('chunk_index')}: {e}")

    path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return done, errors


def run_local(test_one: str | None, execute: bool) -> None:
    client = make_openai()
    files = sorted(EMBEDDED_FOLDER.glob("*.json"))
    if test_one:
        files = [EMBEDDED_FOLDER / test_one]
        if not files[0].exists():
            raise FileNotFoundError(files[0])

    print("=" * 60)
    print("Generate Summaries (LOCAL)")
    print("=" * 60)
    print(f"Mode  : {'EXECUTE' if execute else 'DRY-RUN'}")
    print(f"Model : {CHAT_MODEL}")
    print(f"Files : {len(files)}")

    total_done = 0
    total_errors = 0

    for path in files:
        try:
            done, errors = process_local_file(client, path, execute)
            total_done += done
            total_errors += errors
        except Exception as e:
            total_errors += 1
            print(f"\nERROR file {path.name}: {e}")

    print("\n" + "=" * 60)
    print("DONE LOCAL")
    print("=" * 60)
    print(f"Summaries written : {total_done}")
    print(f"Errors            : {total_errors}")


# =====================================================
# SUPABASE SYNC
# =====================================================

def run_sync(test_one: str | None, execute: bool) -> None:
    mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    by_json = {info["json_file"]: info for info in mapping.values()}

    files = sorted(EMBEDDED_FOLDER.glob("*.json"))
    if test_one:
        files = [EMBEDDED_FOLDER / test_one]

    print("=" * 60)
    print("Sync Summaries -> Supabase")
    print("=" * 60)
    print(f"Mode  : {'EXECUTE' if execute else 'DRY-RUN'}")
    print(f"Files : {len(files)}")

    total_done = 0
    total_errors = 0
    sb = make_supabase()

    for path in files:
        info = by_json.get(path.name)
        if not info:
            print(f"\nSKIP (no map): {path.name}")
            continue
        try:
            done, errors, sb = sync_file(sb, path, info["document_id"], execute)
            total_done += done
            total_errors += errors
        except Exception as e:
            total_errors += 1
            print(f"\nERROR {path.name}: {e}")
            time.sleep(3)
            sb = make_supabase()

    print("\n" + "=" * 60)
    print("DONE SYNC")
    print("=" * 60)
    print(f"Synced : {total_done}")
    print(f"Errors : {total_errors}")


def fetch_chunk_rows(sb: Client, document_id: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    page = 200
    while True:
        end = start + page - 1
        result = (
            sb.table("document_chunks")
            .select("id,chunk_index,summary")
            .eq("document_id", document_id)
            .order("chunk_index")
            .range(start, end)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def sync_file(
    sb: Client,
    path: Path,
    document_id: str,
    execute: bool,
) -> tuple[int, int, Client]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    local = {
        c["chunk_index"]: c["summary"]
        for c in chunks
        if isinstance(c.get("summary"), str) and c["summary"].strip()
    }

    print(f"\nSync: {path.name}")
    print(f"  document_id : {document_id}")
    print(f"  local summaries: {len(local)}/{len(chunks)}")

    # retry fetch with client refresh
    db_rows = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            db_rows = fetch_chunk_rows(sb, document_id)
            break
        except Exception as e:
            print(f"  fetch retry {attempt}: {type(e).__name__}")
            time.sleep(min(2 ** attempt, 30))
            sb = make_supabase()
    if db_rows is None:
        raise RuntimeError("Could not fetch chunk rows")

    print(f"  db chunks   : {len(db_rows)}")

    # Only update rows still missing summary
    to_update = []
    for row in db_rows:
        if row.get("summary"):
            continue
        summary = local.get(row["chunk_index"])
        if summary:
            to_update.append((row["id"], summary))

    print(f"  to update   : {len(to_update)}")

    if not to_update:
        print("  SKIP (already synced)")
        return 0, 0, sb

    if not execute:
        print("  DRY-RUN")
        return 0, len(to_update), sb

    done = 0
    errors = 0

    for chunk_id, summary in to_update:
        updated = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                sb.table("document_chunks").update(
                    {"summary": summary}
                ).eq("id", chunk_id).execute()
                updated = True
                break
            except Exception as e:
                time.sleep(min(2 ** attempt, 20))
                sb = make_supabase()
                if attempt == MAX_RETRIES:
                    errors += 1
                    print(f"  ERROR id={chunk_id[:8]}: {e}")

        if updated:
            done += 1
            if done == 1 or done % 50 == 0 or done == len(to_update):
                print(f"  synced {done}/{len(to_update)}")

    return done, errors, sb

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Generate into local JSON")
    parser.add_argument("--sync", action="store_true", help="Push local summaries to DB")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--test-one", type=str, default=None)
    args = parser.parse_args()

    if not args.local and not args.sync:
        # default: local first
        args.local = True

    if args.local:
        run_local(args.test_one, args.execute)
    if args.sync:
        run_sync(args.test_one, args.execute)


if __name__ == "__main__":
    main()
