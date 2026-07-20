#!/usr/bin/env python3
"""Generate nomic-embed-text (768-dim) embeddings for all products in data/products.json.

Binary output (data/product_embeddings.bin):
  Header  : 4 bytes magic b'RFEM' | 4 bytes uint32 count | 4 bytes uint32 dims
  Per entry: 12 bytes ID (3 × uint32 crc32 hash) | dims × 4 bytes float32 embedding

JSON index (data/product_embeddings_index.json):
  {"<itemID>": <position_index>, ...}   — position_index is 0-based entry number

Resume: re-run any time; already-embedded itemIDs are skipped.
Concurrency: 16 threads by default (~50ms per embed → ~4-5 min for 66K products).

Usage:
  python scripts/generate_embeddings.py
  THREADS=8 python scripts/generate_embeddings.py
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
DIMS = 768
THREADS = int(os.environ.get("THREADS", "16"))
BATCH_SIZE = 200

REPO_ROOT = Path(__file__).parent.parent
PRODUCTS_JSON = REPO_ROOT / "data" / "products.json"
BIN_OUT = REPO_ROOT / "data" / "product_embeddings.bin"
IDX_OUT = REPO_ROOT / "data" / "product_embeddings_index.json"

HEADER_SIZE = 12                   # 4 magic + 4 count + 4 dims
ID_SIZE = 12                       # 3 × uint32
ENTRY_SIZE = ID_SIZE + DIMS * 4    # 12 + 3072 = 3084 bytes per product


def embed_text(text: str) -> list[float]:
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    vec = data["embedding"]
    if len(vec) != DIMS:
        raise ValueError(f"Expected {DIMS} dims, got {len(vec)}")
    return vec


def item_id_hash(item_id: str) -> tuple[int, int, int]:
    enc = item_id.encode()
    h1 = zlib.crc32(enc) & 0xFFFFFFFF
    h2 = zlib.crc32(enc[::-1] or b"\x00") & 0xFFFFFFFF
    h3 = zlib.crc32(enc + b"\xff") & 0xFFFFFFFF
    return h1, h2, h3


def process_one(args: tuple) -> tuple | None:
    raw_idx, item_id, text = args
    try:
        vec = embed_text(text)
        return raw_idx, item_id, vec
    except Exception as exc:
        print(f"  FAIL [{item_id}]: {exc}", flush=True)
        return None


def write_header(fh, count: int, dims: int) -> None:
    pos = fh.tell()
    fh.seek(0)
    fh.write(struct.pack("<4sII", b"RFEM", count, dims))
    fh.seek(pos)  # restore so subsequent writes append correctly


def main() -> None:
    print(f"Loading {PRODUCTS_JSON} ...", flush=True)
    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    total = len(raw)
    print(f"Products: {total:,}", flush=True)

    # Load existing index (resume support)
    existing: dict[str, int] = {}
    if IDX_OUT.exists():
        with open(IDX_OUT, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Resume: {len(existing):,} already embedded", flush=True)

    # Validate existing binary file matches index
    if BIN_OUT.exists() and existing:
        expected = HEADER_SIZE + len(existing) * ENTRY_SIZE
        actual = BIN_OUT.stat().st_size
        if actual != expected:
            print(f"WARNING: binary size mismatch (expected {expected}, got {actual}). Starting fresh.", flush=True)
            existing = {}
            BIN_OUT.unlink()

    # Build task list: one entry per unique itemID, skip already-done ones
    tasks = []
    queued_ids: set[str] = set()
    for p in raw:
        item_id = str(p[5] or "")
        if not item_id or item_id in existing or item_id in queued_ids:
            continue
        queued_ids.add(item_id)
        name = str(p[0] or "")
        category = str(p[2] or "")
        text = f"{name} {category}".strip() or name or "product"
        tasks.append((None, item_id, text))

    to_do = len(tasks)
    done_at_start = len(existing)
    print(f"To embed: {to_do:,}  |  Threads: {THREADS}  |  Batch: {BATCH_SIZE}", flush=True)

    if to_do == 0:
        print("Nothing to do — all products already embedded.", flush=True)
        return

    est_min = to_do * 0.05 / THREADS / 60
    print(f"Estimated: ~{est_min:.1f} min", flush=True)

    # Open binary file (create fresh or append)
    mode = "r+b" if BIN_OUT.exists() and existing else "w+b"
    bin_fh = open(BIN_OUT, mode)
    if mode == "w+b":
        # Write placeholder header; fill in count at end
        bin_fh.write(struct.pack("<4sII", b"RFEM", 0, DIMS))

    # Track next position (= number of already-written entries)
    next_pos = len(existing)
    bin_fh.seek(HEADER_SIZE + next_pos * ENTRY_SIZE)

    start = time.time()
    success = 0
    fail = 0

    try:
        for batch_start in range(0, to_do, BATCH_SIZE):
            batch = tasks[batch_start : batch_start + BATCH_SIZE]

            with ThreadPoolExecutor(max_workers=THREADS) as executor:
                futs = {executor.submit(process_one, t): t for t in batch}
                for fut in as_completed(futs):
                    result = fut.result()
                    if result is None:
                        fail += 1
                        continue
                    _, item_id, vec = result
                    h1, h2, h3 = item_id_hash(item_id)
                    entry = struct.pack("<3I", h1, h2, h3)
                    entry += struct.pack(f"<{DIMS}f", *vec)
                    bin_fh.write(entry)
                    existing[item_id] = next_pos
                    next_pos += 1
                    success += 1

            # Flush binary + save index checkpoint after each batch
            bin_fh.flush()
            write_header(bin_fh, next_pos, DIMS)
            bin_fh.flush()
            with open(IDX_OUT, "w", encoding="utf-8") as f:
                json.dump(existing, f)

            elapsed = time.time() - start
            total_done = done_at_start + success
            pct = total_done / total * 100
            rate = success / elapsed if elapsed > 0 else 0.001
            eta_min = (to_do - success) / rate / 60
            print(
                f"  {total_done:,}/{total:,} ({pct:.1f}%)  "
                f"rate={rate:.1f}/s  ETA={eta_min:.1f}m  errors={fail}",
                flush=True,
            )

    finally:
        # Always write final header and close cleanly
        write_header(bin_fh, next_pos, DIMS)
        bin_fh.close()

    file_mb = BIN_OUT.stat().st_size / 1024 / 1024
    print(f"\nDone: {success:,} new embeddings, {fail} errors", flush=True)
    print(f"Binary : {BIN_OUT}  ({file_mb:.1f} MB)", flush=True)
    print(f"Index  : {IDX_OUT}  ({len(existing):,} entries)", flush=True)


if __name__ == "__main__":
    main()
