"""Normalise LivePortrait's legacy expression templates for Owen auditions.

The bundled semantic templates carry motion only, while current LivePortrait
expects eye/lip ratio arrays as well.  We add neutral (closed-mouth, alert)
arrays solely to make the templates load; the template's own motion remains
unchanged.  This is an audition utility, not a production animation system.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ROOT / ".face-runtime" / "LivePortrait" / "assets" / "examples" / "driving"
OUT = ROOT / ".face-runtime" / "owen_templates"

TEMPLATES = {"guarded": "aggrieved.pkl", "considering": "shy.pkl", "answering": "talking.pkl"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source_name in TEMPLATES.items():
        with (DRIVERS / source_name).open("rb") as source:
            template = pickle.load(source)
        frames = template["n_frames"]
        template.setdefault("c_eyes_lst", [np.array([[0.4, 0.4]], dtype=np.float32) for _ in range(frames)])
        template.setdefault("c_lip_lst", [np.array([[0.0]], dtype=np.float32) for _ in range(frames)])
        with (OUT / f"owen_{name}.pkl").open("wb") as target:
            pickle.dump(template, target)
        print(f"Wrote {name}: {frames} frames")


if __name__ == "__main__":
    main()
