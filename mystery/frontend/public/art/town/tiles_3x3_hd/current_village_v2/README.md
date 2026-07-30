# Current Village 3×3 Overworld — Seamless Master

`current_village_v2` is one continuous 6144×4608 master landscape, sliced
only after rendering into nine 2048×1536 external tiles. Roads, shorelines,
hedges, lighting, and terrain therefore cross tile boundaries without joins.

`B2` is the village centre. Its matching cutaway is rendered from the same
master composition, so switching at close zoom keeps all surrounding geometry
fixed while revealing the village interiors.

This is elevated painterly-realistic map artwork. The 32px logical grid does
not make it pixel art and these tiles must not be used as cinematic Places
backgrounds. Places follows `docs/scene_asset_bible.md`.

The prior `current_village_v1` set has been superseded and removed from the
active art tree. Historical copies may exist in version control or external
archives, but prompts and runtime code must not target it.
