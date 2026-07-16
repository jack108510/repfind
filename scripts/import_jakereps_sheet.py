#!/usr/bin/env python3
"""Import direct-link products from the public jakereps Kakobuy Google Sheet.

Only appends rows where the sheet bootstrap exposes a real Weidian itemID.
Products are stored in compact repfind format:
[name, price_usd, category, image_url, platform, external_id]
"""
import json
import re
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

SHEET_ID = "1NcGuWEeQavIn4bBoe9zxkRVAUuvTqZVRazjlkLFBpBg"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
# Public/readable tabs observed in the document.
SHEET_GIDS = [
    "1662963815",  # Trending Now
    "1627836856",  # Mobile version
    "1496246457",  # Update
    "1191615136",  # Shoes
    "404558673",   # Accessories
    "1118654988",  # Hoodies and Pants
    "1507165154",  # Coats and Jackets
]
PRODUCTS_PATH = Path("data/products.json")
CATEGORY = "Community Sheet"


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", "replace")


def clean_name(name: str) -> str:
    name = name.strip()
    name = name.replace(r"\n", " ").replace("\n", " ")
    name = re.sub(r"^\s*\d+\s*[、.)-]\s*", "", name).strip()
    return re.sub(r"\s+", " ", name)


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_name(name).lower()).strip()


def build_price_lookup() -> dict[str, deque[float]]:
    """Read gviz tab values and map visible product names to their USD prices."""
    prices: dict[str, deque[float]] = defaultdict(deque)
    for gid in SHEET_GIDS:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&gid={gid}"
        try:
            text = fetch_url(url)
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
        except Exception:
            continue
        for row in data.get("table", {}).get("rows", []):
            vals = [(cell or {}).get("v") if cell else None for cell in row.get("c", [])]
            for i, val in enumerate(vals):
                if not isinstance(val, str):
                    continue
                name = clean_name(val)
                if not name or name.upper() == "LINK" or len(name) < 2:
                    continue
                # Sheet layouts are usually: name, optional blank, LINK, CNY, USD.
                for link_offset in (1, 2):
                    if i + link_offset < len(vals) and vals[i + link_offset] == "LINK":
                        usd_idx = i + link_offset + 2
                        usd_value = vals[usd_idx] if usd_idx < len(vals) else None
                        if isinstance(usd_value, (int, float)):
                            prices[norm_name(name)].append(round(float(usd_value), 2))
                        break
    return prices


def extract_products(source: str, price_lookup: dict[str, deque[float]]):
    products = []
    seen = set()

    for match in re.finditer(r"itemID%3D(\d+)", source):
        item_id = match.group(1)
        if item_id in seen:
            continue
        seen.add(item_id)

        before = source[max(0, match.start() - 1600):match.start()]
        after = source[match.end():match.end() + 1800]

        raw_values = re.findall(r'\\"3\\":\[2,\\"([^\\"]+)\\"\]', before)
        candidates = []
        for value in raw_values:
            value = value.strip()
            lower = value.lower()
            if not value or value == "LINK" or "http" in lower:
                continue
            if any(skip in lower for skip in (
                "exchange rate", "do not delete", "best finds", "click on", "product", "price", "image"
            )):
                continue
            if re.fullmatch(r"[0-9]+(?:[,.][0-9]+)?\$", value):
                continue
            candidates.append(value)
        if not candidates:
            continue
        name = clean_name(candidates[-1])
        if not name or name.upper() in {"LINK", "PRICE", "IMAGE"}:
            continue

        price_usd = 0.0
        literal_price = re.search(r'\\"3\\":\[2,\\"([0-9]+(?:,[0-9]+)?)\$\\"\]', after)
        if literal_price:
            price_usd = float(literal_price.group(1).replace(",", "."))
        else:
            usd_cell = re.search(
                r'\[null,\d+,null,\d+,null,\d+,\[\{\\"1\\":3,\\"3\\":([0-9.]+)\}\],\[4,\\"#,##0\.00\[\$\$\]\\"\]\]',
                after,
            )
            if usd_cell:
                price_usd = round(float(usd_cell.group(1)), 2)
            else:
                key = norm_name(name)
                if price_lookup.get(key):
                    price_usd = price_lookup[key].popleft()
                else:
                    cny_cell = re.search(r'\\"3\\":\[\{\\"1\\":3,\\"3\\":([0-9.]+)\}\]', after)
                    if cny_cell:
                        price_usd = round(float(cny_cell.group(1)) / 6.5, 2)

        image_url = ""
        image_match = re.search(r'https://[^\\"\]\s<>]+\.(?:jpg|jpeg|png|webp)', after, re.I)
        if image_match:
            image_url = image_match.group(0).replace("\\/", "/")

        products.append([name, price_usd, CATEGORY, image_url, "weidian", item_id])

    return products


def main():
    source = fetch_url(SHEET_URL)
    extracted = extract_products(source, build_price_lookup())

    existing = json.loads(PRODUCTS_PATH.read_text())
    by_id = {str(row[5]): row for row in existing if len(row) > 5}

    new_products = []
    updated_existing = 0
    for row in extracted:
        item_id = str(row[5])
        if item_id in by_id:
            # Keep the importer idempotent and repair rows imported by older versions.
            old = by_id[item_id]
            if old[2] == CATEGORY and (old[0] != row[0] or old[1] != row[1] or old[3] != row[3]):
                old[:6] = row
                updated_existing += 1
        else:
            new_products.append(row)
            by_id[item_id] = row

    if new_products or updated_existing:
        PRODUCTS_PATH.write_text(json.dumps(existing + new_products, ensure_ascii=False, separators=(",", ":")))

    print(json.dumps({
        "extracted_direct_ids": len(extracted),
        "new_products_appended": len(new_products),
        "updated_existing_sheet_rows": updated_existing,
        "total_products_after": len(existing) + len(new_products),
        "zero_price_rows": sum(1 for row in extracted if not row[1]),
        "sample_new": new_products[:10],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
