#!/usr/bin/env python3
"""Regenerate the dramatic stingers in frontend/public/audio/stingers/.

The stingers had the same defect as the old UI sounds, for the same reason: they
were bare oscillator tones. Measured before this script existed:

    contradiction_locked   99.5% of energy below 250 Hz, centroid 131 Hz
    pressure_cracking      99.9% below 250 Hz, centroid  69 Hz
    case_failed           100.0% below 250 Hz, centroid 121 Hz
    intro_tension         100.0% below 250 Hz, centroid  62 Hz

Every one had *zero* energy above 4 kHz and a crest factor of 3-5. A laptop or
phone driver cannot reproduce a 69 Hz sine, so it distorts instead - which is
why a moment meant to feel like dread instead sounded like a fault.

The fix is not simply "move everything up". Low notes are fine, and dread needs
them; what is fatal is a low note with *no harmonics*, because then all the
energy really is down where nothing can reproduce it. A bowed string at E2
(82 Hz) puts harmonics at 165, 247, 330, 412 Hz and up, so a small speaker
renders the note through its harmonics and the ear supplies the missing
fundamental. That is how real instruments survive bad speakers. So these are
built from:

  * bowed()   - detuned unison voices with independent vibrato and pitch drift,
                a body-resonance filter, and bow noise. The detuning and drift
                are what stop it sounding like a synthesiser: no two voices in a
                real section are ever exactly in tune or exactly in phase.
  * bell()    - inharmonic modal partials, because a bell's overtones are not
                integer multiples and that inharmonicity is its identity.
  * impact()  - noise excitation into a modal body, as in generate_ui_sfx.py.

Key: E minor, taken from the assets being replaced (case_solved was a G-B-E
triad, clue_discovered an A-E fifth), so these still sit with the ambient beds
and with whatever the player has already learned to associate.

Usage:
    python3 tools/generate_stingers.py --analyse
    python3 tools/generate_stingers.py --only case_solved clue_discovered
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_ui_sfx import (  # noqa: E402
    SR,
    analyse,
    ad_env,
    band_noise,
    finish,
    modal,
    n_samples,
    norm,
    place,
    t_axis,
    write_wav,
)

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend",
    "public",
    "audio",
    "stingers",
)

# E natural minor, plus G#3 for the Picardy third in case_solved.
E2, E3, E4, E5 = 82.41, 164.81, 329.63, 659.26
F3 = 174.61          # b2 against E - bleak, deliberately unresolved
G3, G4 = 196.00, 392.00
GS3 = 207.65         # G#3: minor becomes major
A3, A4, A5 = 220.00, 440.00, 880.00
B2, B3, B4 = 123.47, 246.94, 493.88
C4 = 261.63          # b6 - dread
BB3 = 233.08         # tritone against E
D4 = 293.66

# A string section's body resonances. Broad and modest: steep peaks here read as
# a formant filter sweep rather than an instrument.
BODY = [(300.0, 5.0, 2.5), (460.0, 4.0, 3.0), (700.0, 3.0, 3.0), (1100.0, 2.5, 3.0), (2600.0, 2.0, 2.0)]


# --------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------

def resonate(x: np.ndarray, peaks) -> np.ndarray:
    """Apply fixed resonant peaks: peaks = [(freq, gain_db, q), ...]."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    h = np.ones_like(f)
    safe = np.maximum(f, 1e-9)
    for freq, gain_db, q in peaks:
        ratio = safe / freq - freq / safe
        h += (10 ** (gain_db / 20) - 1) / (1 + (q * ratio) ** 2)
    return np.fft.irfft(X * h, len(x))


def arc(dur: float, attack: float, release: float, hold: float = 0.0, curve: float = 1.6) -> np.ndarray:
    """Swell envelope: rise over `attack`, hold, then fall over `release`."""
    t = t_axis(dur)
    rise = np.clip(t / max(attack, 1e-6), 0, 1) ** curve
    start = attack + hold
    fall = np.clip(1 - (t - start) / max(release, 1e-6), 0, 1) ** curve
    return rise * np.where(t < start, 1.0, fall)


def bowed(
    dur: float,
    freq: float,
    rng,
    voices: int = 4,
    detune: float = 9.0,
    brightness: float = 3200.0,
    vibrato=(5.2, 11.0, 0.18),
    drift: float = 3.5,
    bow: float = 0.09,
) -> np.ndarray:
    """A small bowed-string section on one note.

    detune  - unison spread in cents
    vibrato - (rate_hz, depth_cents, onset_s); depth ramps in, as a player's does
    drift   - slow random-walk intonation wander in cents, independent per voice

    The harmonic series is a sawtooth (1/k) with a further 6 dB/oct tilt above
    `brightness`, then passed through BODY. 12 dB/oct total is about right for
    bowed strings; steeper than that and the 1-4 kHz band empties out, which is
    the band that carries presence on a small speaker. Summing partials directly
    rather than filtering an oscillator keeps it alias-free at any pitch.
    """
    n = n_samples(dur)
    t = t_axis(dur)
    out = np.zeros(n)
    rate_hz, depth_cents, onset = vibrato
    for _ in range(voices):
        f0 = freq * 2 ** (rng.uniform(-detune, detune) / 1200)
        rate = rate_hz * rng.uniform(0.92, 1.08)
        depth = depth_cents * np.clip((t - onset) / 0.35, 0, 1)
        vib = depth * np.sin(2 * np.pi * rate * t + rng.uniform(0, 2 * np.pi))
        walk = band_noise(n, rng, hi=3.0, order=1)
        walk = walk / (np.max(np.abs(walk)) or 1.0) * drift
        inst = f0 * 2 ** ((vib + walk) / 1200)
        theta = 2 * np.pi * np.cumsum(inst) / SR
        voice = np.zeros(n)
        for k in range(1, 400):
            if k * f0 > SR * 0.45:
                break
            amp = (1.0 / k) / np.sqrt(1.0 + (k * f0 / brightness) ** 2)
            if amp < 2e-4:
                break
            voice += amp * np.sin(k * theta + rng.uniform(0, 2 * np.pi))
        out += voice
    out = resonate(out, BODY)
    if bow > 0:
        # Bow noise sits with the note, not on top of it: same band as the upper
        # partials, and it is the thing that says "hair on string" rather than
        # "oscillator".
        out = norm(out) + norm(band_noise(n, rng, lo=1600, hi=7000)) * bow
    return out


def chord(dur: float, freqs, rng, gains=None, **kw) -> np.ndarray:
    y = np.zeros(n_samples(dur))
    for i, freq in enumerate(freqs):
        y += bowed(dur, freq, rng, **kw) * (gains[i] if gains else 1.0)
    return y


def bell(dur: float, freq: float, rng, decay: float = 0.7, strike: float = 0.30) -> np.ndarray:
    """Struck bell: inharmonic partials plus a strike transient.

    The ratios are deliberately not integers. Integer ratios give an organ pipe;
    the stretched, slightly irrational series is what the ear hears as metal.
    """
    ratios = [
        (1.000, 1.00, 1.00), (2.003, 0.55, 0.72), (3.011, 0.36, 0.54),
        (4.174, 0.23, 0.40), (5.433, 0.15, 0.30), (6.796, 0.10, 0.22),
        (8.211, 0.06, 0.16),
    ]
    spec = [(freq * r, a, decay * d) for r, a, d in ratios]
    y = modal(dur, spec, rng, detune=0.004) * ad_env(dur, 0.0015, decay)
    if strike > 0:
        n = n_samples(min(dur, 0.02))
        hit = band_noise(n, rng, lo=freq * 1.5, hi=11000) * np.exp(-np.arange(n) / (SR * 0.0012))
        y[:n] += norm(hit) * np.max(np.abs(y)) * strike
    return y


def impact(dur: float, freq: float, rng, spec=None, noise_band=(200, 4000), noise: float = 0.5) -> np.ndarray:
    """Struck drum/metal: a short noise excitation into a modal body.

    The fundamental is deliberately *not* the loudest mode. A modal bank whose
    strongest, longest-decaying partial is its fundamental dumps nearly all its
    energy below 250 Hz - which is how the old accusation_submitted ended up
    99.9% sub-250. Real drums are carried by their upper modes and by the strike
    itself; the fundamental is felt, not heard, and a laptop cannot deliver it
    anyway.
    """
    # Timpani-like ratios by default; the head is not harmonic either.
    ratios = spec or [(1.000, 0.70, 1.00), (1.504, 0.85, 0.72), (1.742, 0.70, 0.60),
                      (2.000, 0.52, 0.48), (2.245, 0.36, 0.38), (2.494, 0.24, 0.30),
                      (2.800, 0.15, 0.24)]
    decay = dur * 0.45
    y = modal(dur, [(freq * r, a, decay * d) for r, a, d in ratios], rng, detune=0.01)
    y *= ad_env(dur, 0.0006, decay)
    scale = float(np.max(np.abs(y))) or 1.0
    # The strike: a hard transient, plus a mid-band 'thwack' that is what
    # actually survives on a small speaker.
    n = n_samples(min(dur, 0.05))
    hit = band_noise(n, rng, lo=noise_band[0], hi=noise_band[1]) * np.exp(-np.arange(n) / (SR * 0.006))
    y[:n] += norm(hit) * scale * noise
    n = n_samples(min(dur, 0.09))
    body = band_noise(n, rng, lo=320, hi=2600) * np.exp(-np.arange(n) / (SR * 0.020))
    y[:n] += norm(body) * scale * noise * 0.7
    return y


def tilt(x: np.ndarray, pivot: float = 260.0, low_db: float = -6.0) -> np.ndarray:
    """Low shelf: attenuate below `pivot` so the harmonics carry the pitch.

    This is the 'missing fundamental' effect used deliberately. Take a sawtooth
    at E2 (82 Hz): its first three harmonics are all under 250 Hz and carry ~88%
    of its power, so however rich it looks on paper, a laptop driver gets almost
    nothing it can reproduce and distorts. Shelving the bottom down shifts the
    balance onto harmonics the speaker *can* render, and the ear still hears E2.
    A good speaker loses some weight; that is the right trade for a game played
    mostly on laptops.
    """
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 10 ** (low_db / 20)
    r2 = (f / pivot) ** 2
    return np.fft.irfft(X * (g + (1 - g) * r2 / (1 + r2)), len(x))


def finish_st(y: np.ndarray, peak: float, hp: float = 105.0, shelf_db: float = -6.0, pivot: float = 260.0):
    """finish() with the low shelf applied first."""
    return finish(tilt(y, pivot, shelf_db), peak=peak, hp=hp)


def tremolo(y: np.ndarray, rng, rate: float = 7.5, depth: float = 0.55, jitter: float = 0.18) -> np.ndarray:
    """Bow tremolo. The jitter matters - a metronomic tremolo reads as an LFO."""
    n = len(y)
    t = np.arange(n) / SR
    wobble = band_noise(n, rng, hi=6.0, order=1)
    wobble = wobble / (np.max(np.abs(wobble)) or 1.0) * jitter
    phase = 2 * np.pi * rate * (t + np.cumsum(wobble) / SR)
    return y * (1.0 - depth * 0.5 * (1 - np.cos(phase)))


# --------------------------------------------------------------------------
# The stingers
# --------------------------------------------------------------------------

def make_clue_discovered(rng):
    """A realisation. Rising, bright, the most-played cue in the game."""
    dur = 0.90
    y = np.zeros(n_samples(dur))
    place(y, chord(dur, [A3, E4], rng, vibrato=(5.4, 10.0, 0.15)) * arc(dur, 0.16, 0.42, hold=0.12), 0.0, 0.70)
    place(y, bell(0.80, A5, rng, decay=0.34), 0.07, 0.85)
    place(y, bell(0.66, E5 * 2, rng, decay=0.26, strike=0.22), 0.21, 0.45)
    return finish_st(y, peak=0.62, hp=110, shelf_db=-3.0)


def make_contradiction_locked(rng):
    """A lie caught. Dark, decisive, over quickly."""
    dur = 0.94
    y = np.zeros(n_samples(dur))
    place(y, chord(dur, [E2, BB3], rng, gains=[1.0, 0.45], brightness=2200,
                   vibrato=(4.6, 7.0, 0.20)) * arc(dur, 0.09, 0.50, hold=0.10), 0.0, 0.80)
    # Dull struck metal - inharmonic and stretched, no ring.
    place(
        y,
        impact(0.55, 392.0, rng,
               spec=[(1.0, 1.0, 1.0), (1.47, 0.7, 0.75), (2.09, 0.5, 0.55),
                     (2.76, 0.32, 0.42), (3.61, 0.2, 0.30), (4.83, 0.12, 0.22)],
               noise_band=(400, 6000), noise=0.65),
        0.035,
        0.85,
    )
    return finish_st(y, peak=0.66, hp=110, shelf_db=-8.0)


def make_pressure_defensive(rng):
    """Unease, held back. Quiet - this fires often and must not fatigue."""
    dur = 1.15
    y = np.zeros(n_samples(dur))
    body = chord(dur, [B3, C4], rng, gains=[1.0, 0.55], brightness=2600,
                 vibrato=(6.0, 8.0, 0.10), bow=0.07)
    place(y, tremolo(body, rng, rate=7.8, depth=0.5) * arc(dur, 0.22, 0.55, hold=0.14), 0.0, 1.0)
    return finish_st(y, peak=0.46, hp=130, shelf_db=-7.0, pivot=230.0)


def make_pressure_cracking(rng):
    """Someone starting to break: a strained high note over a drone, unresolved.

    The strain is literal - the vibrato widens and the pitch creeps sharp, which
    is what a player under pressure actually does.
    """
    dur = 1.19
    n = n_samples(dur)
    y = np.zeros(n)
    place(y, bowed(dur, E2, rng, brightness=1900, vibrato=(4.2, 5.0, 0.3), bow=0.03)
          * arc(dur, 0.20, 0.45, hold=0.30), 0.0, 0.62)
    high = bowed(dur, B4, rng, voices=3, detune=14.0, brightness=4200,
                 vibrato=(6.4, 26.0, 0.12), drift=7.0, bow=0.12)
    # Creep sharp by ~35 cents across the cue.
    high *= 1.0
    sharp = np.linspace(0.0, 1.0, n) ** 2
    y += norm(high) * arc(dur, 0.28, 0.40, hold=0.18) * (0.55 + 0.25 * sharp)
    place(y, band_noise(n_samples(0.5), rng, lo=2200, hi=9000) * arc(0.5, 0.3, 0.18), 0.62, 0.10)
    return finish_st(y, peak=0.58, hp=120, shelf_db=-6.0)


def make_accusation_submitted(rng):
    """The decision is made. One impact, a stab of strings, cut off."""
    dur = 0.80
    y = np.zeros(n_samples(dur))
    place(y, impact(0.62, E2 * 2, rng, noise_band=(150, 3000), noise=0.6), 0.0, 1.0)
    # The strings back the impact rather than competing with it - a stab whose
    # sustain is as loud as its attack stops reading as a stab.
    place(y, chord(0.70, [E3, B3], rng, brightness=2800, vibrato=(4.0, 6.0, 0.4))
          * arc(0.70, 0.03, 0.34, hold=0.18), 0.005, 0.42)
    return finish_st(y, peak=0.70, hp=115, shelf_db=-9.0)


def make_case_solved(rng):
    """Resolution, but a melancholy one: E minor turning to E major.

    A Picardy third. It resolves without being triumphant, which is the tone the
    end of a murder case wants - somebody is still dead.
    """
    dur = 2.10
    y = np.zeros(n_samples(dur))
    # Phase 1: E minor, unsettled.
    place(y, chord(1.15, [E3, G3, B3], rng, brightness=2800, vibrato=(5.0, 9.0, 0.25))
          * arc(1.15, 0.30, 0.42, hold=0.30), 0.0, 0.72)
    # Phase 2: the third lifts to G#, and E4 opens the voicing out.
    place(y, chord(1.30, [E3, GS3, B3, E4], rng, gains=[1.0, 0.9, 0.8, 0.6],
                   brightness=3200, vibrato=(4.8, 8.0, 0.25))
          * arc(1.30, 0.35, 0.62, hold=0.20), 0.86, 0.85)
    place(y, bell(1.05, E5, rng, decay=0.48, strike=0.20), 1.00, 0.34)
    return finish_st(y, peak=0.60, hp=110, shelf_db=-6.0)


def make_case_failed(rng):
    """Bleak. Three chords descending onto an unresolved minor second."""
    dur = 2.10
    y = np.zeros(n_samples(dur))
    place(y, chord(0.95, [B3, G3], rng, brightness=2400, vibrato=(4.6, 8.0, 0.25))
          * arc(0.95, 0.22, 0.40, hold=0.22), 0.0, 0.70)
    place(y, chord(0.95, [A3, F3], rng, brightness=2100, vibrato=(4.4, 8.0, 0.25))
          * arc(0.95, 0.24, 0.40, hold=0.18), 0.62, 0.68)
    # Lands on E against F: a minor second, so it never settles.
    place(y, chord(0.95, [E3, F3], rng, gains=[1.0, 0.55], brightness=1800,
                   vibrato=(4.0, 6.0, 0.30)) * arc(0.95, 0.28, 0.52, hold=0.05), 1.20, 0.62)
    return finish_st(y, peak=0.56, hp=110, shelf_db=-8.0)


def make_intro_tension(rng):
    """Opening unease: a drone with a high note arriving over it. Cuts, not fades."""
    dur = 1.25
    y = np.zeros(n_samples(dur))
    place(y, bowed(dur, E2, rng, brightness=1800, vibrato=(3.8, 4.0, 0.4), bow=0.03)
          * arc(dur, 0.45, 0.22, hold=0.50), 0.0, 0.75)
    high = bowed(0.85, B4, rng, voices=3, brightness=3800, vibrato=(5.8, 14.0, 0.15), bow=0.10)
    place(y, tremolo(high, rng, rate=8.4, depth=0.42) * arc(0.85, 0.35, 0.16, hold=0.30), 0.34, 0.45)
    return finish_st(y, peak=0.58, hp=115, shelf_db=-8.0)


def make_intro_discovery(rng):
    """The moment the case opens: an impact, a bell, and a suspended chord."""
    dur = 1.55
    y = np.zeros(n_samples(dur))
    place(y, impact(0.70, E2 * 2, rng, noise_band=(180, 3500), noise=0.55), 0.0, 0.85)
    # E-A-B: suspended, so it poses a question rather than answering one.
    place(y, chord(1.45, [E3, A3, B3], rng, gains=[1.0, 0.75, 0.65], brightness=2900,
                   vibrato=(4.8, 8.0, 0.30)) * arc(1.45, 0.38, 0.60, hold=0.30), 0.05, 0.70)
    place(y, bell(1.10, E5, rng, decay=0.50, strike=0.24), 0.28, 0.38)
    return finish_st(y, peak=0.64, hp=110, shelf_db=-6.0)


def make_intro_drama(rng):
    """The full opening: stab, swell, struck metal, decay."""
    dur = 2.10
    y = np.zeros(n_samples(dur))
    place(y, impact(0.85, E2 * 2, rng, noise_band=(150, 4000), noise=0.6), 0.0, 0.90)
    body = chord(1.90, [E3, B3, E4], rng, gains=[1.0, 0.8, 0.55], brightness=3000,
                 vibrato=(5.2, 10.0, 0.22))
    place(y, tremolo(body, rng, rate=7.0, depth=0.35) * arc(1.90, 0.40, 0.85, hold=0.35), 0.04, 0.78)
    place(
        y,
        impact(0.95, 329.63, rng,
               spec=[(1.0, 1.0, 1.0), (1.47, 0.7, 0.75), (2.09, 0.5, 0.55),
                     (2.76, 0.32, 0.42), (3.61, 0.2, 0.30)],
               noise_band=(400, 7000), noise=0.6),
        0.52,
        0.42,
    )
    return finish_st(y, peak=0.68, hp=115, shelf_db=-8.0)


SOUNDS = {
    "clue_discovered_short": (make_clue_discovered, 31),
    "contradiction_locked_short": (make_contradiction_locked, 32),
    "pressure_defensive_short": (make_pressure_defensive, 33),
    "pressure_cracking_short": (make_pressure_cracking, 34),
    "accusation_submitted_short": (make_accusation_submitted, 35),
    "case_solved_short": (make_case_solved, 36),
    "case_failed_short": (make_case_failed, 37),
    "intro_tension": (make_intro_tension, 38),
    "intro_discovery": (make_intro_discovery, 39),
    "intro_drama": (make_intro_drama, 40),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    ap.add_argument("--analyse", action="store_true", help="print metrics after writing")
    ap.add_argument("--only", nargs="*", help="only regenerate these stingers")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    names = args.only or list(SOUNDS)
    for name in names:
        key = name if name in SOUNDS else f"{name}_short"
        if key not in SOUNDS:
            raise SystemExit(f"unknown stinger: {name}")
        build, seed = SOUNDS[key]
        path = os.path.join(args.out, f"{key}.wav")
        write_wav(path, build(np.random.default_rng(seed)), np.random.default_rng(seed + 1000))
        print(f"wrote {path}")

    if args.analyse:
        print()
        for name in names:
            key = name if name in SOUNDS else f"{name}_short"
            print(analyse(os.path.join(args.out, f"{key}.wav")))


if __name__ == "__main__":
    main()
