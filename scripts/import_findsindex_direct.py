#!/usr/bin/env python3
"""Import direct Weidian product links from FindsIndex into RepFind.

RepFind product row format:
[name, price_usd, category, image_url, platform, external_id]

This importer is intentionally incremental and idempotent:
- Reads existing data/products.json
- Fetches FindsIndex API pages
- Fetches detail pages to extract the real weidian itemID/sourceUrl
- Dedupes by (platform, itemID)
- Appends only real direct Weidian links
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRODUCTS_PATH = REPO / "data" / "products.json"
CACHE_PATH = REPO / "data" / "findsindex_source_cache.json"
API = "https://findsindex.com/api/products"
DETAIL = "https://findsindex.com/products/{slug}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
CNY_TO_USD = 7.2

# Prioritize the stuff people actually search and categories that are valuable for RepFind.
DEFAULT_KEYWORDS = [
    "asics", "new balance", "dior", "chrome hearts", "patek", "windbreaker",
    "jordan", "nike", "adidas", "yeezy", "bag", "jacket", "watch", "jersey",
    "hoodie", "sneaker", "shoe", "clog", "vans", "salomon", "balenciaga",
]


def fetch_text(url: str, timeout: int = 30, headers: dict | None = None) -> str:
    hdrs = {"User-Agent": UA, "Accept": "text/html,application/json,*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_json(url: str, timeout: int = 30) -> dict:
    return json.loads(fetch_text(url, timeout=timeout))


def load_products() -> list:
    return json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))


def save_products(products: list) -> None:
    PRODUCTS_PATH.write_text(json.dumps(products, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def product_key(row: list) -> tuple[str, str] | None:
    if len(row) < 6:
        return None
    platform = str(row[4] or "").strip().lower()
    item_id = str(row[5] or "").strip()
    if not platform or not item_id:
        return None
    return platform, item_id


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    return title[:180]


def price_usd(item: dict) -> float:
    raw = item.get("priceMin") or item.get("priceMax") or 0
    try:
        val = float(raw)
    except Exception:
        return 0.0
    currency = (item.get("currency") or "CNY").upper()
    if currency == "USD":
        return round(val, 2)
    if currency == "CNY":
        return round(val / CNY_TO_USD, 2)
    return round(val, 2)


def category_name(item: dict) -> str:
    cat = item.get("primaryCategory") or {}
    if isinstance(cat, dict) and cat.get("name"):
        return str(cat["name"])
    if item.get("aiBrandName"):
        return str(item["aiBrandName"])
    return "FindsIndex"


def useful_for_priority(item: dict, keywords: list[str]) -> bool:
    if not keywords:
        return True
    hay = " ".join(str(item.get(k) or "") for k in ("title", "description", "aiBrandName"))
    brand = item.get("brand") or {}
    cat = item.get("primaryCategory") or {}
    if isinstance(brand, dict):
        hay += " " + str(brand.get("name") or "")
    if isinstance(cat, dict):
        hay += " " + str(cat.get("name") or "") + " " + str(cat.get("slug") or "")
    hay = hay.lower()
    return any(k.lower() in hay for k in keywords)


def extract_weidian_id_from_detail(slug: str, cache: dict) -> str | None:
    if slug in cache:
        return cache[slug] or None
    url = DETAIL.format(slug=urllib.parse.quote(slug))
    for headers in ({"RSC": "1"}, None):
        try:
            html = fetch_text(url, timeout=25, headers=headers)
        except Exception:
            continue
        patterns = [
            r"weidian\.com/item\.html\?itemID=(\d+)",
            r"weidian\.com%2Fitem\.html%3FitemID%3D(\d+)",
            r"sourceUrl\\?\"\s*:\s*\\?\"https://weidian\.com/item\.html\?itemID=(\d+)",
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                cache[slug] = m.group(1)
                return cache[slug]
    cache[slug] = ""
    return None


def fetch_candidates(start_page: int, pages: int, limit: int, keywords: list[str]) -> list[dict]:
    candidates: list[dict] = []
    seen_slugs = set()
    end_page = start_page + pages - 1
    for page in range(start_page, end_page + 1):
        url = f"{API}?page={page}&limit={limit}"
        data = fetch_json(url)
        items = data.get("data") or []
        for item in items:
            slug = item.get("slug")
            if not slug or slug in seen_slugs:
                continue
            if (item.get("status") or "active") != "active":
                continue
            if not useful_for_priority(item, keywords):
                continue
            seen_slugs.add(slug)
            candidates.append(item)
        print(f"page {page}/{end_page}: candidates={len(candidates)}", file=sys.stderr)
    return candidates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-page", type=int, default=1, help="FindsIndex API page to start scanning from")
    ap.add_argument("--pages", type=int, default=30, help="FindsIndex API pages to scan")
    ap.add_argument("--limit", type=int, default=100, help="Products per FindsIndex API page")
    ap.add_argument("--max-new", type=int, default=500, help="Stop after appending this many new products")
    ap.add_argument("--workers", type=int, default=8, help="Concurrent detail fetches")
    ap.add_argument("--all", action="store_true", help="Do not keyword-prioritize candidates")
    ap.add_argument("--dry-run", action="store_true", help="Do not write products.json")
    args = ap.parse_args()

    start = time.time()
    products = load_products()
    existing = {product_key(row) for row in products if product_key(row)}
    cache = load_cache()
    keywords = [] if args.all else DEFAULT_KEYWORDS
    candidates = fetch_candidates(args.start_page, args.pages, args.limit, keywords)

    appended = []
    skipped_existing = 0
    failed_source = 0

    def resolve(item: dict):
        slug = str(item.get("slug") or "")
        item_id = extract_weidian_id_from_detail(slug, cache) if slug else None
        return item, item_id

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(resolve, item) for item in candidates]
        for i, fut in enumerate(as_completed(futures), 1):
            item, item_id = fut.result()
            if not item_id:
                failed_source += 1
                continue
            key = ("weidian", str(item_id))
            if key in existing:
                skipped_existing += 1
                continue
            row = [
                clean_title(item.get("title") or item.get("originalTitle") or item.get("slug") or "FindsIndex product"),
                price_usd(item),
                category_name(item),
                item.get("mainImage") or "",
                "weidian",
                str(item_id),
            ]
            products.append(row)
            appended.append(row)
            existing.add(key)
            if len(appended) % 100 == 0 and not args.dry_run:
                save_products(products)
                save_cache(cache)
                print(f"autosaved appended={len(appended)} total={len(products)}", file=sys.stderr)
            if len(appended) >= args.max_new:
                break
            if i % 100 == 0:
                save_cache(cache)
                print(f"resolved {i}/{len(futures)} appended={len(appended)}", file=sys.stderr)

    save_cache(cache)
    if appended and not args.dry_run:
        save_products(products)

    result = {
        "scanned_candidates": len(candidates),
        "new_products_appended": len(appended),
        "skipped_existing": skipped_existing,
        "failed_source_lookup": failed_source,
        "total_products_after": len(products),
        "dry_run": args.dry_run,
        "seconds": round(time.time() - start, 1),
        "sample_new": appended[:10],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
