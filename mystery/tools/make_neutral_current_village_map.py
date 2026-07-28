"""Create a geometry-identical, neutrally lit current_village_v2 map set."""

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "frontend/public/art/town/tiles_3x3_hd/current_village_v2"
OUTPUT_DIR = ROOT / "frontend/public/art/town/tiles_3x3_hd/current_village_v2_neutral"
SOURCE_FULL = SOURCE_DIR / "town_overworld_full_current_village_v2.png"
SOURCE_CUTAWAY = SOURCE_DIR / "town_overworld_full_current_village_v2_cutaway.png"


def neutral_grade(image: Image.Image) -> Image.Image:
    """Lift shadow detail and remove the heavy blue cast without repainting."""
    image = ImageOps.autocontrast(image.convert("RGB"), cutoff=(0.15, 0.1))
    gamma = 0.62
    lut = [round(255 * ((value / 255) ** gamma)) for value in range(256)]
    image = image.point(lut * 3)
    image = ImageEnhance.Color(image).enhance(0.78)
    image = ImageEnhance.Contrast(image).enhance(0.93)

    red, green, blue = image.split()
    red = red.point([min(255, round(value * 1.07 + 3)) for value in range(256)])
    green = green.point([min(255, round(value * 1.04 + 2)) for value in range(256)])
    blue = blue.point([min(255, round(value * 0.91)) for value in range(256)])
    return Image.merge("RGB", (red, green, blue))


def save_mosaic(master: Image.Image, suffix: str = "") -> None:
    rows = ("A", "B", "C")
    for row_index, row in enumerate(rows):
        for col_index in range(3):
            cell = f"{row}{col_index + 1}"
            tile = master.crop((
                col_index * 2048,
                row_index * 1536,
                (col_index + 1) * 2048,
                (row_index + 1) * 1536,
            ))
            tile.save(
                OUTPUT_DIR / f"town_overworld_{cell}_current_village_v2_neutral{suffix}.png",
                optimize=True,
            )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full = neutral_grade(Image.open(SOURCE_FULL))
    cutaway = neutral_grade(Image.open(SOURCE_CUTAWAY))

    full.save(OUTPUT_DIR / "town_overworld_full_current_village_v2_neutral.png", optimize=True)
    cutaway.save(
        OUTPUT_DIR / "town_overworld_full_current_village_v2_neutral_cutaway.png",
        optimize=True,
    )
    save_mosaic(full)

    # Only B2 changes in the close-zoom mosaic.
    b2_cutaway = cutaway.crop((2048, 1536, 4096, 3072))
    b2_cutaway.save(
        OUTPUT_DIR / "town_overworld_B2_current_village_v2_neutral_cutaway.png",
        optimize=True,
    )

    preview = full.copy()
    preview.thumbnail((2048, 1536), Image.Resampling.LANCZOS)
    preview.save(OUTPUT_DIR / "current_village_v2_neutral_preview.png", optimize=True)
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()
