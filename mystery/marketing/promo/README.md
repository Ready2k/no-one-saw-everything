# No One Saw Everything — teaser package

The three master files are all 28 seconds, H.264/AAC MP4, and are built only
from the repository's game artwork, UI captures, and bundled audio.

| File | Format | Style | Intended placement |
| --- | --- | --- | --- |
| `teaser-01-cinematic.mp4` | 1920×1080 | Slow-burn, prestige mystery | YouTube pre-roll / store hero |
| `teaser-02-social-short.mp4` | 1080×1920 | Caption-led, rapid hook | YouTube Shorts / TikTok / Reels |
| `teaser-03-gameplay.mp4` | 1920×1080 | Clear mechanic-led pitch | YouTube ad / product page |

## Copy map

- Cinematic: the emotional promise — a dead man, a village of secrets, an accusation.
- Social Short: the instant hook — death at 08:12, then the rewind/interrogate/connect loop.
- Gameplay: the product promise — fair-play deduction, with the full player loop in 28 seconds.

The CTA deliberately says **COMING SOON** because no launch platform, date, or
store link is currently represented in the project. Replace that final line in
`scripts/promo/create_teasers.sh` once those details are confirmed, then rebuild.

## Rebuild

From the repository root:

```bash
./scripts/promo/create_teasers.sh
```

The script clears only `marketing/promo/.work/`, its own disposable render cache.
