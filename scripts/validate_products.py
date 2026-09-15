#!/usr/bin/env python3
"""Validate and optionally deduplicate RepFind's published product catalog.

Rows are [name, price_usd, category, image_url, platform, external_id].
The canonical identity is (platform, external_id). With --fix, duplicate snapshots
are replaced by the most complete row; marketplace IDs are never rewritten.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPO / "data" / "products.json"


def key(row: list) -> tuple[str, str] | None:
    if not isinstance(row, list) or len(row) < 6:
        return None
    platform = str(row[4] or "weidian").strip().lower()
    external_id = str(row[5] or "").strip()
    return (platform, external_id) if external_id else None


def valid_image(value: object) -> bool:
    try:
        return urlparse(str(value or "")).scheme in {"http", "https"}
    except ValueError:
        return False


def quality(row: list) -> tuple[int, int, int, int]:
    """Prefer complete rows, then useful titles; preserve input order on ties."""
    title = str(row[0] or "").strip() if len(row) > 0 else ""
    try:
        has_price = float(row[1]) > 0
    except (TypeError, ValueError, IndexError):
        has_price = False
    category = str(row[2] or "").strip() if len(row) > 2 else ""
    image = row[3] if len(row) > 3 else ""
    return (int(valid_image(image)), int(has_price), int(bool(category)), min(len(title), 180))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--fix", action="store_true", help="write one best row per platform/external ID")
    args = parser.parse_args()

    rows = json.loads(args.path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("catalog root must be a JSON array", file=sys.stderr)
        return 2

    malformed = [i for i, row in enumerate(rows) if key(row) is None]
    counts = Counter(k for row in rows if (k := key(row)) is not None)
    duplicate_excess = sum(count - 1 for count in counts.values())

    missing_title = sum(not str(row[0] or "").strip() for row in rows if isinstance(row, list) and len(row) >= 6)
    missing_category = sum(not str(row[2] or "").strip() for row in rows if isinstance(row, list) and len(row) >= 6)
    missing_image = sum(not valid_image(row[3]) for row in rows if isinstance(row, list) and len(row) >= 6)
    nonpositive_price = 0
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        try:
            nonpositive_price += float(row[1]) <= 0
        except (TypeError, ValueError):
            nonpositive_price += 1

    if args.fix:
        best: dict[tuple[str, str], list] = {}
        order: list[tuple[str, str]] = []
        for row in rows:
            row_key = key(row)
            if row_key is None:
                continue
            if row_key not in best:
                best[row_key] = row
                order.append(row_key)
            elif quality(row) > quality(best[row_key]):
                best[row_key] = row
        rows = [best[row_key] for row_key in order]
        args.path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        counts = Counter(key(row) for row in rows)
        duplicate_excess = sum(count - 1 for count in counts.values())

    report = {
        "rows": len(rows),
        "unique_listings": len(counts),
        "duplicate_excess": duplicate_excess,
        "malformed_rows": len(malformed),
        "missing_titles": missing_title,
        "missing_categories": missing_category,
        "missing_or_invalid_images": missing_image,
        "nonpositive_prices": nonpositive_price,
        "fixed": args.fix,
    }
    print(json.dumps(report, indent=2))
    return 1 if malformed or duplicate_excess else 0


if __name__ == "__main__":
    raise SystemExit(main())
