#!/usr/bin/env python3
"""
FindsIndex → Weidian ID resolver for repfind.
Downloads FindsIndex catalog, matches by image hash, fetches weidian IDs from detail pages.
Updates products.json in-place with resolved numeric weidian IDs.
"""
import urllib.request, json, re, time, sys, os, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

PRODUCTS_FILE = '/Users/jackserver/repfind/data/products.json'
CACHE_DIR = '/tmp/repfind_resolver'
os.makedirs(CACHE_DIR, exist_ok=True)

def get_img_hash(url):
    """Extract the unique image hash from a geilicdn URL."""
    m = re.search(r'(open\d+-\d+-[0-9a-f]+)', url)
    return m.group(1) if m else None

def fetch_json(url, timeout=15):
    """Fetch JSON from URL with retry."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                raise

def fetch_text(url, headers=None, timeout=15):
    """Fetch raw text from URL with retry."""
    for attempt in range(3):
        try:
            hdrs = {'User-Agent': 'Mozilla/5.0'}
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, headers=hdrs)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                return None

def fetch_weidian_id(slug):
    """Fetch a FindsIndex product detail page and extract the weidian itemID."""
    url = f'https://findsindex.com/products/{slug}'
    html = fetch_text(url, headers={'RSC': '1'}, timeout=15)
    if html:
        m = re.search(r'weidian\.com/item\.html\?itemID=(\d+)', html)
        if m:
            return m.group(1)
        # Also try JSON-LD sourceUrl
        m2 = re.search(r'"sourceUrl":\s*"(https://weidian\.com/item\.html\?itemID=(\d+))"', html)
        if m2:
            return m2.group(2)
    return None

# ===================== PHASE 1: Load our products =====================
print("=" * 60)
print("PHASE 1: Loading products.json")
print("=" * 60)

with open(PRODUCTS_FILE) as f:
    products = json.load(f)

print(f"Loaded {len(products):,} products")

# Build our image hash index
our_hash_to_idx = {}  # hash → index in products array
for i, p in enumerate(products):
    h = get_img_hash(p[3])
    if h:
        our_hash_to_idx[h] = i

# Track which products already have numeric IDs
already_numeric = set()
for i, p in enumerate(products):
    id_val = str(p[5]) if p[5] else ''
    if id_val.isdigit():
        already_numeric.add(i)

print(f"Products with image hashes: {len(our_hash_to_idx):,}")
print(f"Already have numeric weidian IDs: {len(already_numeric):,}")
print(f"Need resolution: {len(products) - len(already_numeric):,}")

# ===================== PHASE 2: Download FindsIndex catalog =====================
print("\n" + "=" * 60)
print("PHASE 2: Downloading FindsIndex catalog")
print("=" * 60)

# Check for cached catalog
cache_file = os.path.join(CACHE_DIR, 'fi_catalog.json')
if os.path.exists(cache_file):
    print(f"Loading cached catalog from {cache_file}")
    with open(cache_file) as f:
        fi_catalog = json.load(f)  # hash → slug
    print(f"Cached: {len(fi_catalog):,} entries")
else:
    fi_catalog = {}
    
    # Get total pages
    data = fetch_json('https://findsindex.com/api/products?page=1&limit=100')
    total_pages = data['meta']['totalPages']
    total_items = data['meta']['total']
    print(f"FindsIndex total: {total_items:,} items across {total_pages:,} pages")
    
    # We only need pages where our products match. Based on testing,
    # pages 1-1500 have most matches. Scan all but stop early if match rate drops.
    consecutive_empty = 0
    batch_start = time.time()
    
    for page in range(1, min(total_pages + 1, 1800)):  # cap at 1800 pages
        try:
            url = f'https://findsindex.com/api/products?page={page}&limit=100'
            data = fetch_json(url)
            
            matches_this_page = 0
            for item in data['data']:
                h = get_img_hash(item.get('mainImage', ''))
                if h and h in our_hash_to_idx:
                    fi_catalog[h] = item['slug']
                    matches_this_page += 1
            
            if matches_this_page == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0
            
            # Progress every 50 pages
            if page % 50 == 0 or page == 1:
                elapsed = time.time() - batch_start
                rate = page / elapsed
                remaining = (total_pages - page) / rate / 60
                print(f"  Page {page}/{total_pages} | Catalog: {len(fi_catalog):,} matches | "
                      f"Rate: {rate:.1f}/s | ETA: {remaining:.0f}min | "
                      f"Empty streak: {consecutive_empty}")
            
            # Stop if 200 consecutive pages with zero matches
            if consecutive_empty >= 200 and page > 500:
                print(f"  Stopping at page {page} - {consecutive_empty} consecutive zero-match pages")
                break
                
        except Exception as e:
            print(f"  Page {page} error: {e}")
            time.sleep(5)
    
    # Save cache
    with open(cache_file, 'w') as f:
        json.dump(fi_catalog, f)
    print(f"Catalog saved: {len(fi_catalog):,} matched entries (cached)")

# ===================== PHASE 3: Resolve weidian IDs =====================
print("\n" + "=" * 60)
print("PHASE 3: Resolving Weidian IDs from detail pages")
print("=" * 60)

# Build list of products needing resolution
# Map: product_idx → slug
needs_resolution = {}
for h, slug in fi_catalog.items():
    if h in our_hash_to_idx:
        idx = our_hash_to_idx[h]
        if idx not in already_numeric:
            needs_resolution[idx] = slug

print(f"Products to resolve: {len(needs_resolution):,}")

# Check for previously resolved cache
resolved_cache = os.path.join(CACHE_DIR, 'resolved_ids.json')
if os.path.exists(resolved_cache):
    with open(resolved_cache) as f:
        resolved = json.load(f)
    print(f"Previously resolved: {len(resolved):,}")
else:
    resolved = {}  # idx (as str) → weidian_id

# Filter out already resolved
to_fetch = {idx: slug for idx, slug in needs_resolution.items() if str(idx) not in resolved}
print(f"Still need to fetch: {len(to_fetch):,}")

# Fetch detail pages with thread pool
lock = Lock()
fetched = 0
found = 0
failed = 0
start_time = time.time()

def resolve_one(item):
    """Fetch detail page for one product and extract weidian ID."""
    global fetched, found, failed
    idx, slug = item
    
    # Skip if already resolved
    if str(idx) in resolved:
        return (idx, None)
    
    wid = fetch_weidian_id(slug)
    
    with lock:
        fetched += 1
        if wid:
            found += 1
            resolved[str(idx)] = wid
        else:
            failed += 1
        
        # Progress every 500
        if fetched % 500 == 0:
            elapsed = time.time() - start_time
            rate = fetched / elapsed
            remaining = (len(to_fetch) - fetched) / rate / 60
            print(f"  Fetched: {fetched:,}/{len(to_fetch):,} | "
                  f"Found: {found:,} | Failed: {failed:,} | "
                  f"Rate: {rate:.1f}/s | ETA: {remaining:.0f}min")
            
            # Save progress every 500
            with open(resolved_cache, 'w') as f:
                json.dump(resolved, f)
    
    return (idx, wid)

# Run with 5 concurrent workers
items_list = list(to_fetch.items())
print(f"Starting {len(items_list):,} detail page fetches with 5 workers...")

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(resolve_one, item): item for item in items_list}
    for future in as_completed(futures):
        try:
            future.result()
        except Exception as e:
            pass

# Final save of resolved IDs
with open(resolved_cache, 'w') as f:
    json.dump(resolved, f)

print(f"\nResolution complete: {found:,} weidian IDs found, {failed:,} failed")

# ===================== PHASE 4: Update products.json =====================
print("\n" + "=" * 60)
print("PHASE 4: Updating products.json")
print("=" * 60)

# Backup
import shutil
backup = PRODUCTS_FILE + '.bak'
shutil.copy2(PRODUCTS_FILE, backup)
print(f"Backup saved: {backup}")

updated = 0
for idx_str, wid in resolved.items():
    idx = int(idx_str)
    if idx < len(products):
        old_id = str(products[idx][5]) if products[idx][5] else ''
        # Only update if old ID wasn't numeric
        if not old_id.isdigit():
            products[idx][5] = wid
            updated += 1

print(f"Updated {updated:,} products with real weidian IDs")

# Count final stats
final_numeric = sum(1 for p in products if str(p[5]).isdigit())
print(f"\nFinal stats:")
print(f"  Total products: {len(products):,}")
print(f"  With direct buy links (numeric weidian IDs): {final_numeric:,}")
print(f"  Search fallback: {len(products) - final_numeric:,}")
print(f"  Improvement: {final_numeric - len(already_numeric):,} new direct links")

# Save
with open(PRODUCTS_FILE, 'w') as f:
    json.dump(products, f, ensure_ascii=False)
print(f"\nSaved to {PRODUCTS_FILE}")
print("DONE!")
