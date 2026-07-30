# Current Village V2 Neutral — Runtime Canonical Map

This directory is the runtime canonical 3×3 overhead tile family selected by
`backend/app/town_map.py`.

- Full world: 6144×4608.
- Logical grid: 192×144 at 32px.
- Cell: 2048×1536, representing 64×48 logical tiles.
- B2 exterior and cutaway use identical geography.
- Global time of day remains code-driven.

The art style is painterly-realistic rural British overhead map artwork.
The 32px value is placement geometry only; do not introduce visible pixel-art,
RPG-sprite, chibi, cartoon, or toy-like rendering.

These images are not cinematic Places backgrounds. Places uses dedicated HD
scene art governed by `docs/scene_asset_bible.md`.
