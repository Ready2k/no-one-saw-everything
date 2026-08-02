"""Create a human-readable location guide over the canonical bird's-eye map."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/art/town/tiles_3x3_hd/current_village_v3_neutral/town_overworld_full_current_village_v3_neutral.png"
OUTPUT = ROOT / "docs/current_village_v3_location_guide.png"

# Coordinates are measured from the current artwork: x, y, width, height in
# the 192x144 editor grid. Named legacy interiors are intentionally excluded:
# the painted roofs do not identify which resident/business owns each plot.
LOCATIONS = {
    "LANDMARK — Village Square": (91, 50, 18, 16),
    "LANDMARK — Fountain": (97, 53, 5, 5),
    "LANDMARK — St. Alder's Church": (67, 36, 21, 18),
    "LANDMARK — Willow Farmhouse": (46, 108, 22, 19),
    "LANDMARK — Western Lake": (7, 44, 47, 42),
    "LANDMARK — Fishery & Docks": (145, 42, 39, 29),
    "LANDMARK — Northern Farms": (27, 4, 53, 29),
    "LANDMARK — North Farmhouse": (111, 9, 19, 16),
    "LANDMARK — Eastern Woodland": (143, 5, 42, 31),
    "LANDMARK — Southern Meadow": (70, 106, 42, 28),
    "LANDMARK — Southern Woodland": (120, 101, 51, 38),
    "ROUTE — Back Lane": (102, 87, 29, 8),
    "PLOT A — The Mallet & Crown": (89, 37, 12, 10),
    "PLOT B — North-centre terrace": (101, 36, 20, 15),
    "PLOT C — North-east house": (125, 35, 19, 17),
    "PLOT D — West shop compound": (71, 52, 18, 20),
    "PLOT E — Whittle & Cross Solicitors": (88, 65, 9, 10),
    "PLOT F — East square building": (108, 52, 17, 20),
    "PLOT G — Western cottages": (64, 69, 23, 22),
    "PLOT H — South-centre cottage": (91, 82, 17, 17),
    "PLOT I — Eastern work yard": (111, 68, 25, 25),
}


def font(size: int, bold: bool = False):
    name = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    return ImageFont.truetype(name, size)


def main() -> None:
    image = Image.open(SOURCE).convert("RGB")
    # Keep the full bird's-eye composition while making it easy to open/share.
    image.thumbnail((3072, 2304), Image.Resampling.LANCZOS)
    scale = image.width / 6144
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = font(34, True)
    label_font = font(18, True)
    small_font = font(16)

    # A compact title strip keeps the guide self-explanatory when detached.
    draw.rounded_rectangle((24, 24, 990, 104), radius=16, fill=(8, 16, 30, 220), outline=(135, 190, 255, 230), width=2)
    draw.text((48, 38), "CURRENT VILLAGE — CORRECTED PLACEMENT GUIDE", font=title_font, fill=(240, 248, 255, 255))
    draw.text((50, 77), "Confirmed landmarks + neutral building plots; no guessed legacy identities", font=small_font, fill=(190, 215, 240, 255))

    # Two columns prevent the legend from obscuring the centre of the map.
    items = list(LOCATIONS.items())
    legend_x = 24
    legend_y = 126
    row_h = 24
    col_w = 430
    panel_h = ((len(items) + 1) // 2) * row_h + 24
    draw.rounded_rectangle((legend_x, legend_y, legend_x + col_w * 2 + 18, legend_y + panel_h), radius=12, fill=(7, 14, 26, 205), outline=(90, 145, 200, 210), width=2)

    for index, (label, (x, y, w, h)) in enumerate(items, start=1):
        px = (x + w / 2) * 32 * scale
        py = (y + h / 2) * 32 * scale
        radius = max(12, int(16 * scale))
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(9, 26, 47, 235), outline=(255, 214, 105, 255), width=3)
        number = str(index)
        bbox = draw.textbbox((0, 0), number, font=label_font)
        draw.text((px - (bbox[2] - bbox[0]) / 2, py - (bbox[3] - bbox[1]) / 2 - 2), number, font=label_font, fill=(255, 244, 190, 255))

        col = (index - 1) // ((len(items) + 1) // 2)
        row = (index - 1) % ((len(items) + 1) // 2)
        tx = legend_x + 18 + col * col_w
        ty = legend_y + 12 + row * row_h
        draw.text((tx, ty), f"{index:02d}  {label}", font=small_font, fill=(238, 244, 252, 255))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, optimize=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
