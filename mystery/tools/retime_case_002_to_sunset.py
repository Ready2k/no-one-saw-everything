"""Shift Case 002 from lunchtime to a 16:30–18:15 sunset timeline."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "backend/app/data/case_002"
TIME_RE = re.compile(r"(?<!\d)([01]\d|2[0-3]):([0-5]\d)(?!\d)")

PHRASE_REPLACEMENTS = (
    ("The lunchtime hour", "The evening hour"),
    ("all lunchtime", "all late afternoon"),
    ("All lunchtime", "All late afternoon"),
    ("lunchtime", "late afternoon"),
    ("Lunchtime", "Late-afternoon"),
    ("Lunch shift", "Evening shift"),
    ("lunch rolls", "evening rolls"),
    ("around midday", "in the late afternoon"),
    ("Midday", "Afternoon"),
    ("morning busk", "late-afternoon busk"),
    ("morning papers", "evening papers"),
    ("morning loaves", "evening loaves"),
    ("morning's produce", "evening's produce"),
    ("cool mornings", "cool evenings"),
    ("good morning", "good afternoon"),
    ("every morning", "every afternoon"),
    ("All morning", "All afternoon"),
    ("all morning", "all afternoon"),
    ("that morning", "that afternoon"),
    ("this morning", "this afternoon"),
    ("half twelve", "half five"),
    ("Half twelve", "Half five"),
    ("half past one", "half past six"),
    ("gone half past one", "gone half past six"),
    ("from eleven this afternoon", "from four this afternoon"),
    ("from eleven", "from four"),
    ("From eleven", "From four"),
)


def shift_time(match: re.Match[str]) -> str:
    hour = (int(match.group(1)) + 5) % 24
    return f"{hour:02d}:{match.group(2)}"


def retime(text: str) -> str:
    text = TIME_RE.sub(shift_time, text)
    for old, new in PHRASE_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def main() -> None:
    case_file = CASE_DIR / "case.json"
    if '"sim_start_time": "16:30"' in case_file.read_text():
        raise SystemExit("Case 002 is already retimed to sunset")
    for path in sorted((*CASE_DIR.glob("*.json"), CASE_DIR / "all.md")):
        path.write_text(retime(path.read_text()))
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
