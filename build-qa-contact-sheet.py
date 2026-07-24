from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "preview-mobile"
OUTPUT = ROOT / "output" / "qa" / "repfind-mobile-checkpoints.jpg"
SOURCES = [
    ("01-welcome.png", "1. Welcome and search"),
    ("02-results.png", "2. Immediate natural browse"),
    ("03-detail.png", "3. Product selection"),
    ("04-kakobuy-live-link.png", "4. Live KakoBuy page — product photo loaded"),
]

CELL_WIDTH = 480
CELL_HEIGHT = 854
GUTTER = 32
HEADER_HEIGHT = 132
LABEL_HEIGHT = 52
CANVAS_WIDTH = CELL_WIDTH * 2 + GUTTER * 3
CANVAS_HEIGHT = HEADER_HEIGHT + (CELL_HEIGHT + LABEL_HEIGHT) * 2 + GUTTER * 3

try:
    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
except OSError:
    title_font = ImageFont.load_default()
    label_font = ImageFont.load_default()

canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "#111827")
draw = ImageDraw.Draw(canvas)
title = "repfind mobile recording — QA checkpoints"
draw.text((GUTTER, 28), title, font=title_font, fill="#f9fafb")
draw.text((GUTTER, 78), "Configured live-link verification: Comme des Garçons T-Shirt / itemID 7778860787", font=label_font, fill="#cbd5e1")

for index, (filename, label) in enumerate(SOURCES):
    source_path = INPUT_DIR / filename
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    image = Image.open(source_path).convert("RGB")
    image.thumbnail((CELL_WIDTH, CELL_HEIGHT), Image.Resampling.LANCZOS)
    column = index % 2
    row = index // 2
    x = GUTTER + column * (CELL_WIDTH + GUTTER)
    y = HEADER_HEIGHT + GUTTER + row * (CELL_HEIGHT + LABEL_HEIGHT + GUTTER)
    cell = Image.new("RGB", (CELL_WIDTH, CELL_HEIGHT), "#020617")
    offset_x = (CELL_WIDTH - image.width) // 2
    offset_y = (CELL_HEIGHT - image.height) // 2
    cell.paste(image, (offset_x, offset_y))
    canvas.paste(cell, (x, y))
    draw.rectangle((x, y, x + CELL_WIDTH, y + CELL_HEIGHT), outline="#334155", width=2)
    draw.text((x, y + CELL_HEIGHT + 13), label, font=label_font, fill="#f8fafc")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUTPUT, quality=92, optimize=True)
print(OUTPUT)
