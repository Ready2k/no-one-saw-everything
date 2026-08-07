"""Build the seamless lifelike v3 village map from approved source edits.

This pipeline is deliberately all-PNG. Runtime tiles are shipped as AVIF, but
AVIF is a *publish* format here, not an intermediate: the chain
v2 -> v2_neutral -> v3_neutral re-encodes the same pixels three times, and
round-tripping it through lossy AVIF measurably degrades the map on every
rebuild (43.0 -> 41.6 -> 40.1 dB PSNR over three generations). Keep the masters
lossless, then convert the finished tiles to AVIF as the last step.

The PNG inputs this reads are no longer in the working tree (they were replaced
by their AVIF publishes). Restore them from git before rebuilding, e.g.
    git checkout <pre-avif-commit> -- mystery/frontend/public/art/town/tiles_3x3_hd/current_village_v2_neutral
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/art/town/tiles_3x3_hd/current_village_v2_neutral"
EDITS = ROOT / "frontend/public/art/town/source_edits/current_village_v3_lifelike"
OUTPUT = ROOT / "frontend/public/art/town/tiles_3x3_hd/current_village_v3_neutral"

EXTERIOR_EDITS = (
    # Preserve the original map's seamless buildings and add only the tiny
    # identity details from the replacement art. Full replacement buildings
    # had a different texture scale and became obvious pasted blocks under
    # the replay's dawn tint, even after exposure and colour matching.
    (
        EDITS / "pub_exterior_neutral_v2.png", 2640, 950, 768, 640,
        ((548, 420), (600, 420), (600, 500), (548, 500)),
        (1.0, 1.0, 1.0),
    ),
    (
        EDITS / "solicitors_exterior_neutral_v2.png", 2600, 1920, 640, 576,
        ((368, 348), (410, 348), (410, 390), (368, 390)),
        (1.0, 1.0, 1.0),
    ),
)
INTERIOR_EDITS = (
    (
        EDITS / "pub_cutaway_neutral_v3.png", 2640, 950, 768, 640,
        ((225, 175), (590, 175), (590, 570), (225, 570)),
        (0.97, 1.0, 1.04),
    ),
    (
        EDITS / "solicitors_cutaway_neutral_v3.png", 2600, 1920, 640, 576,
        ((145, 105), (430, 105), (430, 465), (145, 465)),
        (0.97, 1.0, 1.04),
    ),
)

# Image-generation passes are kept as reviewable source plates.  We never use
# a whole generated tile: even a strong edit can move a road by a few pixels
# and break the 3x3 seams.  Instead, crop the approved lifelike cutaways and
# fit only those buildings back into the authoritative master geometry.
INTERIOR_SOURCE_PLATES = (
    # path, source crop (left, top, right, bottom), target box in the master
    (EDITS / "cutaway_plate_a2_lifelike_v1.png", (130, 650, 540, 1086), (2144, 1056, 704, 480)),
    (EDITS / "cutaway_plate_a2_lifelike_v1.png", (590, 650, 930, 1045), (2800, 1100, 470, 430)),
    (EDITS / "cutaway_plate_a2_lifelike_v1.png", (920, 650, 1390, 1045), (3260, 1080, 500, 450)),
    (EDITS / "cutaway_plate_b2_lifelike_v1.png", (230, 165, 590, 450), (2380, 1770, 500, 420)),
    (EDITS / "cutaway_plate_b2_lifelike_v1.png", (510, 385, 745, 620), (2785, 2040, 360, 390)),
    (EDITS / "cutaway_plate_b2_lifelike_v1.png", (1000, 40, 1395, 325), (3510, 1640, 535, 440)),
    (EDITS / "cutaway_plate_b2_lifelike_v1.png", (810, 300, 1185, 930), (3120, 2070, 650, 720)),
    (EDITS / "cutaway_plate_b2_lifelike_v1.png", (120, 535, 455, 855), (2260, 2210, 470, 530)),
    (EDITS / "cutaway_plate_b3_lifelike_v1.png", (0, 430, 315, 1015), (3770, 2130, 700, 610)),
    (EDITS / "cutaway_plate_a3_lifelike_v1.png", (170, 735, 495, 1086), (4270, 1090, 500, 440)),
    # Willow Farmhouse is intentionally compact: this crop is taken from an
    # edit of the actual C1 exterior, so its shell matches the painted roof.
    (
        EDITS / "cutaway_plate_c1_farmhouse_lifelike_v2.png",
        (1080, 330, 1450, 730),
        (1530, 3520, 518, 430),
    ),
)


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize without distortion, centre-cropping only surplus context."""
    target_w, target_h = size
    source_ratio = image.width / image.height
    target_ratio = target_w / target_h
    if source_ratio > target_ratio:
        crop_w = round(image.height * target_ratio)
        left = (image.width - crop_w) // 2
        image = image.crop((left, 0, left + crop_w, image.height))
    elif source_ratio < target_ratio:
        crop_h = round(image.width / target_ratio)
        top = (image.height - crop_h) // 2
        image = image.crop((0, top, image.width, top + crop_h))
    return image.resize(size, Image.Resampling.LANCZOS)


def colour_balance(image: Image.Image, grade: tuple[float, float, float]) -> Image.Image:
    """Apply a restrained RGB balance before the shared runtime tint."""
    channels = image.split()
    return Image.merge(
        "RGB",
        tuple(
            channel.point(lambda value, scale=scale: min(255, round(value * scale)))
            for channel, scale in zip(channels, grade)
        ),
    )


def composite_edits(master: Image.Image, edits) -> Image.Image:
    result = master.convert("RGB")
    for path, x, y, width, height, mask_polygon, grade in edits:
        patch = cover_resize(Image.open(path).convert("RGB"), (width, height))
        patch = colour_balance(patch, grade)
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(mask_polygon, fill=255)
        result.paste(patch, (x, y), mask.filter(ImageFilter.GaussianBlur(8)))
    return result


def composite_source_plates(master: Image.Image) -> Image.Image:
    """Composite approved lifelike interiors without disturbing map seams."""
    result = master.convert("RGB")
    for path, crop, target in INTERIOR_SOURCE_PLATES:
        x, y, width, height = target
        patch = cover_resize(Image.open(path).convert("RGB").crop(crop), (width, height))
        # A soft inset keeps the canonical roads/hedges authoritative while
        # blending the replacement walls into their original plots.
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        inset = max(10, min(width, height) // 24)
        draw.rounded_rectangle(
            (inset, inset, width - inset, height - inset),
            radius=max(18, inset * 2),
            fill=255,
        )
        result.paste(patch, (x, y), mask.filter(ImageFilter.GaussianBlur(inset)))
    return result


def save_tiles(master: Image.Image, suffix: str = "") -> None:
    for row_index, row in enumerate("ABC"):
        for col_index in range(3):
            cell = f"{row}{col_index + 1}"
            tile = master.crop(
                (
                    col_index * 2048,
                    row_index * 1536,
                    (col_index + 1) * 2048,
                    (row_index + 1) * 1536,
                )
            )
            tile.save(
                OUTPUT / f"town_overworld_{cell}_current_village_v3_neutral{suffix}.png",
                optimize=True,
            )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exterior = composite_edits(
        Image.open(SOURCE / "town_overworld_full_current_village_v2_neutral.png"),
        EXTERIOR_EDITS,
    )
    interior = composite_edits(
        Image.open(SOURCE / "town_overworld_full_current_village_v2_neutral_cutaway.png"),
        INTERIOR_EDITS,
    )
    interior = composite_source_plates(interior)
    exterior.save(OUTPUT / "town_overworld_full_current_village_v3_neutral.png", optimize=True)
    interior.save(
        OUTPUT / "town_overworld_full_current_village_v3_neutral_cutaway.png",
        optimize=True,
    )
    save_tiles(exterior)
    save_tiles(interior, "_cutaway")
    preview = exterior.copy()
    preview.thumbnail((2048, 1536), Image.Resampling.LANCZOS)
    preview.save(OUTPUT / "current_village_v3_neutral_preview.png", optimize=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
