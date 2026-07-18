#!/usr/bin/env python3
"""
repfind — Haul of the Day Generator
====================================
Picks 5 products (one per category), downloads images, and generates
a TikTok-ready carousel (7 slides, 1080x1350, monochrome repfind aesthetic).

Usage:
    python3 generate_haul.py              # Generate today's haul
    python3 generate_haul.py --seed 42    # Reproducible haul
    python3 generate_haul.py --output /custom/path  # Custom output dir

Output:
    ./output/YYYY-MM-DD/
        01_cover.jpg       (you design this — or use placeholder)
        02_sneakers.jpg
        03_bags.jpg
        04_watches.jpg
        05_clothing.jpg
        06_accessories.jpg
        07_end.jpg
        haul_data.json     (metadata: products, prices, captions)
        caption.txt        (TikTok caption + hashtags)
"""

import json, os, sys, random, hashlib, requests, argparse
from datetime import datetime, date
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─── Config ───
SCRIPT_DIR = Path(__file__).parent.resolve()
REPFIND_DIR = SCRIPT_DIR.parent
PRODUCT_DB_PATH = REPFIND_DIR / "data" / "products.json"
LOGO_PATH = REPFIND_DIR / "logo.png"
DEFAULT_OUTPUT = SCRIPT_DIR / "output"

# TikTok carousel dimensions (4:5 portrait — max engagement)
W, H = 1080, 1350

# Monochrome palette (matches repfind.ca)
BG     = (18, 18, 18)
WHITE  = (255, 255, 255)
GRAY   = (140, 140, 140)
DIM    = (90, 90, 90)
SURFACE = (35, 35, 35)
BORDER  = (70, 70, 70)

# 5 haul categories — one product from each for diversity
HAUL_CATEGORIES = {
    'Sneakers': {
        'cats': ['老爹鞋', '跑步鞋'],
        'keywords': ['nike', 'jordan', 'yeezy', 'adidas', 'dunk', 'air max',
                     'air force', 'new balance', 'kobe', 'travis scott'],
    },
    'Bags': {
        'cats': [],
        'keywords': ['bag', 'backpack', 'tote', 'duffel', 'crossbody',
                     'louis vuitton bag', 'gucci bag', 'dior bag'],
    },
    'Watches': {
        'cats': [],
        'keywords': ['watch', 'rolex', 'patek', 'audemars', 'hublot', 'cartier watch'],
    },
    'Clothing': {
        'cats': ['卫衣', '夹克', '毛衣'],
        'keywords': ['hoodie', 'jacket', 'bape', 'essentials', 'fear of god', 'off white'],
    },
    'Accessories': {
        'cats': ['太阳镜', '项链', '手链', '戒指', '帽子'],
        'keywords': ['sunglasses', 'chain', 'ring', 'chrome hearts', 'cartier'],
    },
}

BRANDS = ['nike', 'jordan', 'yeezy', 'adidas', 'louis vuitton', 'gucci',
          'rolex', 'patek', 'bape', 'chrome hearts', 'travis scott',
          'off white', 'dior', 'balenciaga', 'cartier', 'new balance',
          'fear of god', 'essentials']


# ════════════════════════════════════════════════
# PRODUCT SELECTION
# ════════════════════════════════════════════════

def date_seed():
    """Deterministic seed from today's date — same haul all day, different tomorrow."""
    return int(date.today().strftime("%Y%m%d"))


def load_products():
    with open(PRODUCT_DB_PATH) as f:
        return json.load(f)


def pick_products(raw, seed=None):
    """Pick one high-quality product from each category."""
    if seed is None:
        seed = date_seed()
    rng = random.Random(seed)

    picks = {}
    for label, config in HAUL_CATEGORIES.items():
        candidates = []
        for p in raw:
            name = p[0].lower()
            cat = p[2] if len(p) > 2 else ''
            price = p[1] if len(p) > 1 else 0
            img = p[3] if len(p) > 3 else ''

            # Quality filters
            if not img or 'picsum' in img or not price or price < 5:
                continue

            cat_match = any(c in cat for c in config['cats']) if config['cats'] else False
            kw_match = any(kw in name for kw in config['keywords'])
            if not (cat_match or kw_match):
                continue

            # Score: brand names boost, penalize generic/print-on-demand
            score = sum(1 for b in BRANDS if b in name)
            if name.startswith('design '):
                score -= 2

            candidates.append({
                'name': p[0],
                'price': price,
                'cat': cat,
                'img': img,
                'platform': p[4] if len(p) > 4 else 'weidian',
                'id': p[5] if len(p) > 5 else '',
                'score': score + rng.random() * 0.5,
            })

        candidates.sort(key=lambda x: -x['score'])
        if candidates:
            # Pick from top 15 for daily variety while staying high quality
            picks[label] = rng.choice(candidates[:15])
        else:
            print(f"⚠️  No candidates for {label}")

    return picks


def download_images(picks, img_dir):
    """Download product images locally."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    for label, product in picks.items():
        try:
            r = requests.get(product['img'], headers=headers, timeout=15)
            if r.status_code == 200 and len(r.content) > 5000:
                path = img_dir / f"{label.lower()}.jpg"
                with open(path, 'wb') as f:
                    f.write(r.content)
                product['local_img'] = str(path)
            else:
                product['local_img'] = None
        except Exception as e:
            print(f"⚠️  {label} image download failed: {e}")
            product['local_img'] = None
    return picks


# ════════════════════════════════════════════════
# IMAGE GENERATION
# ════════════════════════════════════════════════

def get_font(size, bold=True):
    try:
        return ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size)
    except:
        return ImageFont.load_default()


def truncate(text, font, max_width, draw):
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + '...', font=font) > max_width:
        text = text[:-1]
    return text + '...' if text else ''


def load_logo(max_size=120):
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert('RGBA')
        logo.thumbnail((max_size, max_size), Image.LANCZOS)
        return logo
    return None


def make_cover(output_path, picks):
    """Slide 1: Dark Hero cover — dramatic, minimal, logo-forward."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle radial gradient (lighter in center)
    overlay = Image.new('RGB', (W, H), BG)
    overlay_draw = ImageDraw.Draw(overlay)
    for r in range(600, 0, -10):
        alpha = max(0, 15 - r // 50)
        overlay_draw.ellipse(
            [W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r],
            fill=(BG[0] + alpha, BG[1] + alpha, BG[2] + alpha),
        )
    img = Image.blend(img, overlay, 0.3)
    draw = ImageDraw.Draw(img)

    # Logo centered, slightly above center
    logo_big = load_logo(140)
    if logo_big:
        img.paste(logo_big, ((W - logo_big.width) // 2, 200), logo_big)

    # "repfind" wordmark
    font_brand = get_font(42)
    bbox = draw.textbbox((0, 0), "repfind", font=font_brand)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 370), "repfind", fill=WHITE, font=font_brand)

    # Big title — two lines
    font_title = get_font(82)
    title1 = "HAUL OF"
    title2 = "THE DAY"
    bbox = draw.textbbox((0, 0), title1, font=font_title)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 500), title1, fill=WHITE, font=font_title)
    bbox = draw.textbbox((0, 0), title2, font=font_title)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 590), title2, fill=WHITE, font=font_title)

    # Divider line
    draw.line([(int(W * 0.3), 740), (int(W * 0.7), 740)], fill=DIM, width=2)

    # Stats line
    total = sum(p['price'] for p in picks.values())
    font_stats = get_font(32)
    stats = f"5 REPS  ·  ${total:.0f} VALUE"
    bbox = draw.textbbox((0, 0), stats, font=font_stats)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 780), stats, fill=GRAY, font=font_stats)

    # Category tags
    font_tag = get_font(22)
    cats = " · ".join(picks.keys())
    bbox = draw.textbbox((0, 0), cats, font=font_tag)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, 840), cats, fill=DIM, font=font_tag)

    # Bottom URL + swipe
    font_url = get_font(30)
    bbox = draw.textbbox((0, 0), "repfind.ca", font=font_url)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, H - 140), "repfind.ca", fill=WHITE, font=font_url)

    font_swipe = get_font(24)
    bbox = draw.textbbox((0, 0), "swipe →", font=font_swipe)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, H - 80), "swipe →", fill=GRAY, font=font_swipe)

    img.save(output_path, quality=95)


def make_product_card(label, product, index, total, output_path, logo):
    """Slides 2-6: Individual product cards with branding."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Product image (top 52%)
    prod_img_path = product.get('local_img')
    if prod_img_path and os.path.exists(prod_img_path):
        prod_img = Image.open(prod_img_path).convert('RGB')
        prod_img.thumbnail((int(W * 0.82), int(H * 0.52)), Image.LANCZOS)
        x = (W - prod_img.width) // 2
        y = 140
        img.paste(prod_img, (x, y))

    # Category label (top left)
    font_cat = get_font(26)
    draw.text((50, 65), label.upper(), fill=GRAY, font=font_cat)

    # Slide counter (top right)
    font_count = get_font(24)
    count_text = f"{index}/{total}"
    draw.text((W - 100, 65), count_text, fill=GRAY, font=font_count)

    # Product name
    font_name = get_font(34)
    name = truncate(product['name'], font_name, W - 100, draw)
    draw.text((50, H - 285), name, fill=WHITE, font=font_name)

    # Price
    font_price = get_font(54)
    draw.text((50, H - 215), f"${product['price']:.0f}", fill=WHITE, font=font_price)

    # Platform
    font_plat = get_font(24)
    platform = product.get('platform', 'weidian').title()
    draw.text((50, H - 135), f"Available on {platform}", fill=GRAY, font=font_plat)

    # Branding: small logo + "repfind" (bottom right)
    if logo:
        logo_small = logo.resize((40, 40), Image.LANCZOS)
        img.paste(logo_small, (W - 180, H - 75), logo_small)
    font_brand = get_font(22)
    draw.text((W - 130, H - 68), "repfind", fill=GRAY, font=font_brand)

    img.save(output_path, quality=95)


def make_end_card(picks, output_path, logo):
    """Slide 7: Receipt-style end card with logo + branding."""
    img = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ─── Logo at top ───
    if logo:
        img.paste(logo, ((W - logo.width) // 2, 80), logo)

    # "repfind" wordmark under logo
    font_brand = get_font(36)
    brand_text = "repfind"
    bbox = draw.textbbox((0, 0), brand_text, font=font_brand)
    draw.text(((W - (bbox[2]-bbox[0])) / 2, 220), brand_text, fill=WHITE, font=font_brand)

    # Big "5"
    font_huge = get_font(100)
    font_label = get_font(34)
    big = "5"
    bbox = draw.textbbox((0, 0), big, font=font_huge)
    draw.text(((W - (bbox[2]-bbox[0])) / 2, 300), big, fill=WHITE, font=font_huge)

    reps_text = "REPS IN THIS HAUL"
    bbox = draw.textbbox((0, 0), reps_text, font=font_label)
    draw.text(((W - (bbox[2]-bbox[0])) / 2, 440), reps_text, fill=GRAY, font=font_label)

    # Divider
    draw.line([(150, 540), (W - 150, 540)], fill=DIM, width=1)

    # Receipt breakdown
    cats = list(picks.keys())
    for i, label in enumerate(cats):
        y = 600 + i * 72
        draw.text((150, y), label.upper(), fill=WHITE, font=get_font(30))
        price = f"${picks[label]['price']:.0f}"
        bbox = draw.textbbox((0, 0), price, font=get_font(30))
        pw = bbox[2] - bbox[0]
        draw.text((W - 150 - pw, y), price, fill=GRAY, font=get_font(30))

    # Total
    total = sum(p['price'] for p in picks.values())
    draw.line([(150, 990), (W - 150, 990)], fill=DIM, width=1)
    draw.text((150, 1020), "TOTAL", fill=WHITE, font=get_font(34))
    total_price = f"${total:.0f}"
    bbox = draw.textbbox((0, 0), total_price, font=get_font(34))
    draw.text((W - 150 - (bbox[2]-bbox[0]), 1020), total_price, fill=WHITE, font=get_font(34))

    # URL pill
    font_url = get_font(46)
    url = "repfind.ca"
    bbox = draw.textbbox((0, 0), url, font=font_url)
    uw = bbox[2] - bbox[0]; uh = bbox[3] - bbox[1]
    pill_x = (W - uw) // 2 - 50; pill_y = 1140
    pill_w = uw + 100; pill_h = uh + 44
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                           radius=pill_h // 2, fill=SURFACE, outline=BORDER, width=2)
    draw.text(((W - uw) / 2, pill_y + 22), url, fill=WHITE, font=font_url)

    # CTA
    font_cta = get_font(30)
    cta = "search any of these →"
    bbox = draw.textbbox((0, 0), cta, font=font_cta)
    draw.text(((W - (bbox[2]-bbox[0])) / 2, 1240), cta, fill=GRAY, font=font_cta)

    img.save(output_path, quality=95)


# ════════════════════════════════════════════════
# CAPTION GENERATION
# ════════════════════════════════════════════════

def generate_caption(picks):
    """Generate TikTok caption + hashtags."""
    today = date.today().strftime("%B %-d")
    total = sum(p['price'] for p in picks.values())

    # Build product highlight line
    highlights = []
    for label, product in picks.items():
        # Shorten product name for caption
        short_name = product['name'].split(' BS')[0].split(' Best')[0]
        if len(short_name) > 35:
            short_name = short_name[:35] + '...'
        highlights.append(f"{short_name} (${product['price']:.0f})")

    highlight_lines = "\n".join(f"• {h}" for h in highlights)

    caption = f"""📦 HAUL OF THE DAY — {today}

5 reps, 5 categories. Total value: ${total:.0f}

{highlight_lines}

Find all these + 66,000 more at repfind.ca 🔍

#repfind #reps #sneakerreps #designerreps #haul #sneakerhaul #yeezy #jordan #louisvuitton #rolex #chromehearts #fashionreps #sneakerhead #replica #w2c #sneakercommunity #streetwear #luxuryreps"""

    return caption


# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════

def generate_haul(output_dir=None, seed=None):
    """Generate a complete haul carousel. Returns path to output directory."""
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT / date.today().strftime("%Y-%m-%d")
    else:
        output_dir = Path(output_dir)

    # Dated subdirectory
    if output_dir.exists() and any(output_dir.glob("*.jpg")):
        print(f"⚠️  Haul for {date.today()} already exists at {output_dir}")
        print("   Removing old files to regenerate...")
        for f in output_dir.glob("*.jpg"):
            f.unlink()
        for f in output_dir.glob("*.json"):
            f.unlink()
        for f in output_dir.glob("*.txt"):
            f.unlink()

    slides_dir = output_dir / "slides"
    img_dir = output_dir / "images"
    slides_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    print(f"🎨 Generating haul of the day...")
    print(f"   Date: {date.today().strftime('%Y-%m-%d')}")
    print(f"   Output: {output_dir}")
    print()

    # 1. Pick products
    raw = load_products()
    picks = pick_products(raw, seed)
    print(f"✓ Selected {len(picks)}/5 products")

    # 2. Download images
    picks = download_images(picks, img_dir)
    dl_count = sum(1 for p in picks.values() if p.get('local_img'))
    print(f"✓ Downloaded {dl_count}/{len(picks)} product images")

    # 3. Load logo
    logo = load_logo(120)

    # 4. Generate slides
    total_slides = len(picks) + 2  # cover + products + end
    make_cover(str(slides_dir / "01_cover.jpg"), picks)
    print(f"✓ Slide 1: Cover")

    cats = list(picks.keys())
    for i, label in enumerate(cats):
        path = slides_dir / f"{i+2:02d}_{label.lower()}.jpg"
        make_product_card(label, picks[label], i+2, total_slides, str(path), logo)
        print(f"✓ Slide {i+2}: {label} — {picks[label]['name'][:50]}")

    make_end_card(picks, str(slides_dir / "07_end.jpg"), logo)
    print(f"✓ Slide 7: End card (receipt + branding)")

    # 5. Save metadata + caption
    total = sum(p['price'] for p in picks.values())
    meta = {
        'date': date.today().isoformat(),
        'total_value': round(total, 2),
        'product_count': len(picks),
        'products': picks,
        'slides_dir': str(slides_dir),
    }
    with open(output_dir / "haul_data.json", 'w') as f:
        json.dump(meta, f, indent=2, default=str)

    caption = generate_caption(picks)
    with open(output_dir / "caption.txt", 'w') as f:
        f.write(caption)

    print(f"\n{'='*50}")
    print(f"✅ HAUL COMPLETE")
    print(f"   Slides: {slides_dir}")
    print(f"   Total value: ${total:.2f}")
    print(f"   Caption: {output_dir / 'caption.txt'}")
    print(f"{'='*50}")

    return {
        'output_dir': str(output_dir),
        'slides_dir': str(slides_dir),
        'total_value': round(total, 2),
        'product_count': len(picks),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate repfind Haul of the Day carousel')
    parser.add_argument('--seed', type=int, help='Random seed for reproducible haul')
    parser.add_argument('--output', type=str, help='Custom output directory')
    args = parser.parse_args()

    result = generate_haul(
        output_dir=args.output if args.output else None,
        seed=args.seed,
    )
    print(f"\nResult: {json.dumps(result, indent=2)}")
