# Scenario Interior Expansion v1

This pack supplies two types of reusable art for each new scenario location:

- `*_interior_map_hd.png`: roofless high-angle map art for spatial placement,
  governed by `docs/town_asset_bible.md`.
- `*_search_hd.png`: cinematic 16:9 investigation art for a location search
  scene, governed by `docs/scene_asset_bible.md`.

See `scenario_asset_manifest.json` for stable asset IDs, suggested location
IDs, semantic rooms, affordances, and authoring notes. The assets are neutral:
they contain no preset victim, clue, or suspect, leaving each case author free
to place the story-specific evidence.

The two outputs are not interchangeable. Never enlarge a map interior into a
search scene, and never insert a cinematic search frame into the overhead map.
Neither output may use pixel-art, RPG-sprite, chibi, cartoon, or low-resolution
building-stamp styling.
