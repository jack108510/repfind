#!/usr/bin/env python3
"""
repfind listing verifier — checks random sample of products daily using Playwright.

For each product:
1. Opens the Weidian listing in a headless browser
2. Extracts the current product title
3. Compares against our stored name
4. Flags mismatches (seller swapped product)

Output: JSON report to stdout (for cron delivery) + appends to data/verification_log.jsonl
"""

import json
import random
import re
import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).parent.parent
PRODUCTS_PATH = REPO / "data" / "products.json"
LOG_PATH = REPO / "data" / "verification_log.jsonl"
SAMPLE_SIZE = 500
BATCH_SIZE = 20  # browsers run in parallel batches
TIMEOUT_MS = 12000
DELAY_MS = 200  # delay between batches


def load_products():
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())[:60]


def name_similarity(stored, live):
    """Check if names share key product keywords."""
    a = normalize(stored)
    b = normalize(live)
    if not a or not b:
        return 0

    # If live title is mostly Chinese, we can't reliably compare — assume OK
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', live or ''))
    total_chars = len(live or '')
    if total_chars > 5 and chinese_chars / total_chars > 0.3:
        return 0.5  # Chinese title, can't verify — don't flag

    # Extract brand/product keywords from stored name (only meaningful English words 4+ chars)
    keywords = re.findall(r'[a-z]{4,}', (stored or '').lower())
    live_lower = (live or '').lower()
    # Remove common generic words
    stop = {'design','black','white','grey','with','the','and','for','from','high','quality',
            'cross','border','true','wireless','this','that','have','your','neck','sleeve',
            'round','short','long','full','half','size','blue','green','red','pink','navy'}
    keywords = [k for k in keywords if k not in stop][:10]
    if not keywords:
        return 0.5  # Can't tell, don't flag
    # Check if key brand words appear in live title
    matches = sum(1 for k in keywords if k in live_lower)
    return matches / max(len(keywords), 1)


async def check_batch(playwright, items):
    """Check a batch of products in one browser context."""
    results = []
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-US",
    )

    async def check_one(item):
        stored_name, item_id, platform = item
        page = await context.new_page()
        url = f"https://weidian.com/item.html?itemID={item_id}"
        if platform == "taobao":
            url = f"https://item.taobao.com/item.htm?id={item_id}"
        elif platform == "1688":
            url = f"https://detail.1688.com/offer/{item_id}.html"

        try:
            await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)  # let JS render title
            title = await page.title()
            # Also try to get the main product title element
            try:
                h1 = await page.query_selector("h1")
                if h1:
                    h1_text = await h1.text_content()
                    if h1_text and len(h1_text.strip()) > 3:
                        title = h1_text.strip()
            except:
                pass
            # Clean up site suffixes
            title = re.sub(r'\s*[|-]\s*(Weidian|微店|淘宝|1688|Kakobuy).*$', '', title).strip()

            if not title or title in ("商品详情", "错误页", "Error", "", "登录") or len(title) < 4:
                return {"id": item_id, "status": "unreachable", "stored": stored_name[:80]}
            # If title is just a redirect or SKU code, skip
            if "1688.com" in title or "Loading" in title or title.strip() == item_id:
                return {"id": item_id, "status": "unreachable", "stored": stored_name[:80]}
            return {"id": item_id, "status": "ok", "live": title[:200], "stored": stored_name[:80]}
        except Exception as e:
            return {"id": item_id, "status": "error", "error": str(e)[:80], "stored": stored_name[:80]}
        finally:
            await page.close()

    # Run items concurrently within this batch
    tasks = [check_one(item) for item in items]
    batch_results = await asyncio.gather(*tasks)
    results.extend(batch_results)

    await context.close()
    await browser.close()
    return results


async def run_verification(sample_size=SAMPLE_SIZE):
    from playwright.async_api import async_playwright

    products = load_products()
    checkable = [(str(p[0]), str(p[5]), str(p[4]) if len(p) > 4 else "weidian")
                 for p in products if len(p) > 5 and str(p[5]).isdigit()]
    sample = random.sample(checkable, min(sample_size, len(checkable)))

    results = {
        "checked": 0,
        "ok": 0,
        "mismatch": 0,
        "unreachable": 0,
        "mismatches": [],
    }

    async with async_playwright() as pw:
        # Process in batches
        for i in range(0, len(sample), BATCH_SIZE):
            batch = sample[i:i + BATCH_SIZE]
            batch_results = await check_batch(pw, batch)

            for r in batch_results:
                results["checked"] += 1
                if r["status"] == "unreachable":
                    results["unreachable"] += 1
                elif r["status"] == "error":
                    results["unreachable"] += 1
                elif r["status"] == "ok":
                    sim = name_similarity(r["stored"], r["live"])
                    if sim < 0.15:
                        results["mismatch"] += 1
                        results["mismatches"].append({
                            "id": r["id"],
                            "stored_name": r["stored"],
                            "live_name": r["live"][:100],
                            "similarity": round(sim, 2),
                        })
                    else:
                        results["ok"] += 1

            done = min(i + BATCH_SIZE, len(sample))
            print(f"  ...checked {done}/{len(sample)}", file=sys.stderr)
            await asyncio.sleep(DELAY_MS / 1000)

    return results


if __name__ == "__main__":
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE_SIZE
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"repfind listing verifier — {ts}", file=sys.stderr)
    print(f"Checking {sample_size} random products via headless browser...", file=sys.stderr)

    results = asyncio.run(run_verification(sample_size))
    results["timestamp"] = ts
    results["sample_size"] = sample_size

    # Append to log
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(results, ensure_ascii=False) + "\n")

    # Summary to stdout (for cron delivery)
    if results["mismatches"]:
        print(f"\n⚠️  {results['mismatch']}/{results['checked']} listings mismatched ({results['unreachable']} unreachable)")
        print(f"\nTop mismatches:")
        for m in results["mismatches"][:10]:
            print(f"\n  ID: {m['id']}")
            print(f"  Stored: {m['stored_name']}")
            print(f"  Live:   {m['live_name']}")
            print(f"  Match:  {m['similarity']*100:.0f}%")
        if len(results["mismatches"]) > 10:
            print(f"\n  ...and {len(results['mismatches']) - 10} more")
    else:
        print(f"\n✅ All {results['checked']} sampled listings match ({results['unreachable']} unreachable)")

    print(f"\nStats: {results['ok']} OK · {results['mismatch']} mismatched · {results['unreachable']} unreachable")
