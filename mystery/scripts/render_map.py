"""Render the original the_ville.tmx tilemap to a static PNG.

One-off build tool for the map replay layer: composites the visual tile
layers (skipping logic/marker layers) and writes a downscaled PNG to
mystery/frontend/public/map/the_ville.png. Coordinates used by the game
are in the 719x513 reference space; the output keeps the same aspect
ratio so percentage-based placement is unaffected.

Usage: python3 mystery/scripts/render_map.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
TMX = REPO / "environment/frontend_server/static_dirs/assets/the_ville/visuals/the_ville.tmx"
OUT = REPO / "mystery/frontend/public/map/the_ville.png"
OUT_WIDTH = 1438  # 2x the 719x513 reference space

VISUAL_LAYERS = [
    "Bottom Ground",
    "Exterior Ground",
    "Exterior Decoration L1",
    "Exterior Decoration L2",
    "Interior Ground",
    "Wall",
    "Interior Furniture L1",
    "Interior Furniture L2 ",  # trailing space is in the tmx
    "Foreground L1",
    "Foreground L2",
]

FLIP_H = 0x80000000
FLIP_V = 0x40000000
FLIP_D = 0x20000000


def main() -> None:
    root = ET.parse(TMX).getroot()
    width = int(root.get("width"))
    height = int(root.get("height"))
    tile_w = int(root.get("tilewidth"))
    tile_h = int(root.get("tileheight"))

    # Load tilesets: firstgid -> (image, columns)
    tilesets = []
    for ts in root.findall("tileset"):
        img_el = ts.find("image")
        sheet = Image.open(TMX.parent / img_el.get("source")).convert("RGBA")
        tilesets.append((int(ts.get("firstgid")), sheet, sheet.width // tile_w))
    tilesets.sort(key=lambda t: t[0], reverse=True)

    tile_cache: dict[int, Image.Image] = {}

    def tile_image(gid: int) -> Image.Image | None:
        if gid in tile_cache:
            return tile_cache[gid]
        raw = gid & ~(FLIP_H | FLIP_V | FLIP_D)
        for firstgid, sheet, columns in tilesets:
            if raw >= firstgid:
                index = raw - firstgid
                tx = (index % columns) * tile_w
                ty = (index // columns) * tile_h
                tile = sheet.crop((tx, ty, tx + tile_w, ty + tile_h))
                if gid & FLIP_D:
                    tile = tile.transpose(Image.Transpose.TRANSPOSE)
                if gid & FLIP_H:
                    tile = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if gid & FLIP_V:
                    tile = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                tile_cache[gid] = tile
                return tile
        return None

    canvas = Image.new("RGBA", (width * tile_w, height * tile_h), (24, 26, 33, 255))
    layers = {l.get("name"): l for l in root.findall("layer")}
    for name in VISUAL_LAYERS:
        layer = layers.get(name)
        if layer is None:
            print(f"warning: layer {name!r} not found, skipping")
            continue
        cells = [int(v) for v in layer.find("data").text.replace("\n", "").split(",")]
        for i, gid in enumerate(cells):
            if gid == 0:
                continue
            tile = tile_image(gid)
            if tile is None:
                continue
            x = (i % width) * tile_w
            y = (i // width) * tile_h
            canvas.paste(tile, (x, y), tile)
        print(f"composited {name}")

    out_height = round(canvas.height * OUT_WIDTH / canvas.width)
    scaled = canvas.resize((OUT_WIDTH, out_height), Image.Resampling.LANCZOS)
    scaled.convert("RGB").save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT_WIDTH}x{out_height})")


if __name__ == "__main__":
    main()
